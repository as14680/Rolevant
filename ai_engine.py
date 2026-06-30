"""
AI Engine — Claude-powered job scoring and one-click prep generation.
"""

import json
import os

import anthropic

SCORE_TOOL = {
    "name": "record_job_analysis",
    "description": "Record structured PM job fit analysis for a candidate",
    "input_schema": {
        "type": "object",
        "required": ["fit_score", "recommendation", "strong_matches", "gaps", "score_rationale"],
        "properties": {
            "fit_score": {
                "type": "integer", "minimum": 0, "maximum": 100,
                "description": "0-100 fit score. 90+ = exceptional, 70-89 = strong apply, 50-69 = consider, <50 = skip",
            },
            "recommendation": {
                "type": "string",
                "enum": ["strong_apply", "apply", "maybe", "skip"],
            },
            "strong_matches": {
                "type": "array", "items": {"type": "string"}, "maxItems": 5,
                "description": "Top reasons this candidate is a strong fit",
            },
            "gaps": {
                "type": "array", "maxItems": 4,
                "items": {
                    "type": "object",
                    "required": ["gap", "severity"],
                    "properties": {
                        "gap": {"type": "string"},
                        "severity": {"type": "string", "enum": ["major", "moderate", "minor"]},
                        "how_to_address": {"type": "string"},
                    },
                },
            },
            "score_rationale": {"type": "string", "description": "2-3 sentences explaining the score"},
            "key_selling_points": {
                "type": "array", "items": {"type": "string"}, "maxItems": 4,
            },
            "red_flags": {
                "type": "array", "items": {"type": "string"}, "maxItems": 3,
            },
            "cover_letter_hook": {
                "type": "string",
                "description": "One compelling opening paragraph for a cover letter",
            },
            "networking_targets": {
                "type": "array", "maxItems": 3,
                "items": {
                    "type": "object",
                    "required": ["role"],
                    "properties": {
                        "role": {"type": "string"},
                        "why": {"type": "string"},
                    },
                },
            },
            "seniority_match": {
                "type": "string",
                "enum": ["overqualified", "match", "stretch", "underqualified"],
            },
        },
    },
}


def _get_client() -> anthropic.Anthropic:
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return anthropic.Anthropic(api_key=key)


def _system_prompt(profile: dict, resume: str) -> str:
    linkedin = profile.get("linkedin_url", "")
    linkedin_line = f"\nLinkedIn Profile: {linkedin}" if linkedin else ""
    return f"""You are a senior PM career coach scoring job fit for a product manager candidate.

CANDIDATE:
Name: {profile.get('name','Candidate')}
Title: {profile.get('current_title','Product Manager')}
Years Experience: {profile.get('years_experience',0)}
{linkedin_line}
Skills: {', '.join(profile.get('skills',[]))}
Target Roles: {', '.join(profile.get('target_roles',[]))}
Locations: {', '.join(profile.get('preferred_locations',[]))}
Industries: {', '.join(profile.get('preferred_industries',[]))}
Work Pref: {profile.get('work_preference','remote')}
Salary: {profile.get('salary_range',{}).get('min',0):,}–{profile.get('salary_range',{}).get('max',0):,} USD
Deal Breakers: {', '.join(profile.get('deal_breakers',[]))}
Priorities: {', '.join(profile.get('priorities',[]))}

RESUME:
{resume or '(Not provided — score based on profile only)'}

SCORING CRITERIA (total 100):
• Role/seniority alignment   25%
• Skills overlap             25%
• Domain/industry fit        20%
• Location/remote policy     15%
• Comp alignment             15%

Calibration: 90+ = exceptional match, 70–89 = strong apply, 50–69 = worth considering, <50 = skip.
Be a tough but fair judge. Use the record_job_analysis tool to return your structured analysis."""


def score_job(job: dict, profile: dict, resume: str) -> tuple[int, dict]:
    client = _get_client()
    system = _system_prompt(profile, resume)

    user_msg = f"""Job Title: {job['title']}
Company: {job['company']}
Location: {job.get('location','Unknown')}
Source: {job['source']}
Seniority (detected): {job.get('seniority','unknown')}
YOE Required (detected): {job.get('yoe_required','unknown')}

Description:
{(job.get('description') or '')[:3000]}"""

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=1024,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        tools=[SCORE_TOOL],
        tool_choice={"type": "tool", "name": "record_job_analysis"},
        messages=[{"role": "user", "content": user_msg}],
    )
    for block in resp.content:
        if block.type == "tool_use" and block.name == "record_job_analysis":
            data = block.input
            return data.get("fit_score", 0), data
    return 0, {}


def score_unscored(limit: int = 20) -> int:
    from db import get_jobs, save_analysis, get_setting

    profile_raw = get_setting("profile")
    resume = get_setting("resume") or ""
    profile = json.loads(profile_raw) if profile_raw else {}

    if not resume and not profile:
        print("  No profile/resume — add them in Settings first")
        return 0

    pending = get_jobs(status="new", limit=limit)
    scored = 0
    for job in pending:
        try:
            score, analysis = score_job(job, profile, resume)
            hook = analysis.pop("cover_letter_hook", "")
            save_analysis(job["id"], score, analysis, cover_letter=hook)
            print(f"    {score}/100 — {job['title']} @ {job['company']}")
            scored += 1
        except Exception as e:
            print(f"    Error scoring {job['id']}: {e}")
    return scored


def generate_prep(job: dict) -> tuple[str, str]:
    """One-click prep: returns (tailored_resume, cover_letter)."""
    from db import get_setting

    profile_raw = get_setting("profile")
    resume = get_setting("resume") or ""
    profile = json.loads(profile_raw) if profile_raw else {}

    client = _get_client()

    resp = client.messages.create(
        model="claude-opus-4-7",
        max_tokens=2500,
        system=[{
            "type": "text",
            "text": (
                f"You are a PM career coach. Produce tailored application materials.\n\n"
                f"CANDIDATE PROFILE:\n{json.dumps(profile, indent=2)}\n\n"
                f"ORIGINAL RESUME:\n{resume or '(not provided)'}"
            ),
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{
            "role": "user",
            "content": f"""Create application materials for this PM role.

Job: {job['title']} at {job['company']}
Location: {job.get('location','Unknown')}
Description:
{(job.get('description') or '')[:2500]}

Return ONLY valid JSON with exactly these two keys:
{{
  "tailored_resume": "full resume in markdown, reordered and re-worded to match this role",
  "cover_letter": "3 tight paragraphs — hook referencing company/product, why you're the best PM for this role, call to action"
}}""",
        }],
    )

    try:
        text = resp.content[0].text.strip()
        # strip ```json fences if present
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])
        data = json.loads(text)
        return data.get("tailored_resume", ""), data.get("cover_letter", "")
    except Exception as e:
        print(f"  prep parse error: {e}\nraw: {resp.content[0].text[:200]}")
        return "", ""
