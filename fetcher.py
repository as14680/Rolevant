"""
Job Fetcher — pulls listings from free APIs and RSS feeds.

Sources (no API key needed):
  - Remotive API
  - The Muse API
  - Arbeitnow API
  - RSS: WWR Management, Remote.co PM, HackerNews Jobs, Remotive RSS

Optional (needs JSEARCH_API_KEY from RapidAPI):
  - JSearch — aggregates LinkedIn, Indeed, Glassdoor
"""

import hashlib
import re
import sqlite3
from datetime import datetime, timezone

from typing import Optional
import feedparser
import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; PMDash/1.0)"}
TIMEOUT = 15

PM_KEYWORDS = [
    "product manager", "product management", "product owner",
    "pm ", " pm,", "head of product", "director of product",
    "vp product", "vp of product", "chief product", "group product",
    "lead pm", "principal pm", "staff pm", "technical pm",
    "growth pm", "platform pm", "consumer pm", "enterprise pm",
]


def _job_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:16]


def _strip_html(html: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html or "")
    return re.sub(r"\s+", " ", text).strip()[:6000]


def _parse_date(raw) -> str:
    if not raw:
        return datetime.now(timezone.utc).isoformat()
    if isinstance(raw, (int, float)):
        return datetime.fromtimestamp(raw, tz=timezone.utc).isoformat()
    try:
        import email.utils
        parts = email.utils.parsedate(str(raw))
        if parts:
            return datetime(*parts[:6], tzinfo=timezone.utc).isoformat()
    except Exception:
        pass
    return datetime.now(timezone.utc).isoformat()


def _is_pm_role(title: str) -> bool:
    t = title.lower()
    return any(kw in t for kw in PM_KEYWORDS)


def detect_seniority(title: str) -> str:
    t = title.lower()
    if any(w in t for w in ["director", "vp ", "vp,", "vice president", "head of product", "chief product", "cpo", "group product manager"]):
        return "director+"
    if any(w in t for w in ["principal", "staff pm", "lead pm", "staff product manager"]):
        return "principal"
    if any(w in t for w in ["senior", "sr ", "sr."]):
        return "senior"
    if any(w in t for w in ["junior", "jr ", "jr.", "associate pm", "entry level", "entry-level"]):
        return "junior"
    return "mid"


def extract_yoe(description: str) -> Optional[int]:
    patterns = [
        r"(\d+)\+\s*years?\s*(?:of\s*)?(?:relevant\s*)?(?:product\s*)?(?:management\s*)?experience",
        r"(\d+)\s*\+\s*years?\s*of\s*experience",
        r"minimum\s+(?:of\s+)?(\d+)\s+years?",
        r"at\s+least\s+(\d+)\s+years?",
        r"(\d+)\s*[-–]\s*\d+\s*years?",
    ]
    for p in patterns:
        m = re.search(p, (description or "").lower())
        if m:
            return int(m.group(1))
    return None


def _make_job(source: str, title: str, company: str, location: str, url: str, description: str, posted_at_raw) -> dict:
    return {
        "id": _job_id(url),
        "source": source,
        "title": (title or "Untitled").strip(),
        "company": (company or "Unknown").strip(),
        "location": (location or "Unknown").strip(),
        "url": url,
        "description": description or "",
        "posted_at": _parse_date(posted_at_raw),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "seniority": detect_seniority(title or ""),
        "yoe_required": extract_yoe(description or ""),
    }


# ── Remotive API ──────────────────────────────────────────────────────────────

def fetch_remotive() -> list[dict]:
    jobs = []
    try:
        r = requests.get(
            "https://remotive.com/api/remote-jobs",
            params={"category": "product", "limit": 50},
            headers=HEADERS, timeout=TIMEOUT,
        )
        r.raise_for_status()
        for j in r.json().get("jobs", []):
            title = j.get("title", "") or j.get("job_title", "")
            url = j.get("url", "")
            if not url or not _is_pm_role(title):
                continue
            jobs.append(_make_job(
                "Remotive",
                title,
                j.get("company_name", ""),
                j.get("candidate_required_location", "Remote"),
                url,
                _strip_html(j.get("description", "")),
                j.get("publication_date"),
            ))
    except Exception as e:
        print(f"  [Remotive API] {e}")
    return jobs


# ── RemoteOK API ──────────────────────────────────────────────────────────────

def fetch_remoteok() -> list[dict]:
    jobs = []
    try:
        r = requests.get(
            "https://remoteok.com/api",
            params={"tag": "product-manager"},
            headers={**HEADERS, "Accept": "application/json"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        # First item is usually a notice dict, skip it
        for j in data:
            if not isinstance(j, dict) or not j.get("url"):
                continue
            title = j.get("position", "") or j.get("title", "")
            if not _is_pm_role(title):
                continue
            url = j.get("url", "")
            if url.startswith("/"):
                url = "https://remoteok.com" + url
            tags = j.get("tags", [])
            description = _strip_html(j.get("description", ""))
            jobs.append(_make_job(
                "RemoteOK",
                title,
                j.get("company", "Unknown"),
                j.get("location", "Worldwide"),
                url,
                description,
                j.get("date"),
            ))
    except Exception as e:
        print(f"  [RemoteOK API] {e}")
    return jobs


# ── Arbeitnow API ─────────────────────────────────────────────────────────────

def fetch_arbeitnow() -> list[dict]:
    jobs = []
    try:
        r = requests.get(
            "https://www.arbeitnow.com/api/job-board-api",
            params={"tag": "product-manager"},
            headers=HEADERS, timeout=TIMEOUT,
        )
        r.raise_for_status()
        for j in r.json().get("data", []):
            title = j.get("title", "")
            url = j.get("url", "")
            if not url or not _is_pm_role(title):
                continue
            jobs.append(_make_job(
                "Arbeitnow",
                title,
                j.get("company_name", "Unknown"),
                j.get("location", "Unknown"),
                url,
                _strip_html(j.get("description", "")),
                j.get("created_at"),
            ))
    except Exception as e:
        print(f"  [Arbeitnow API] {e}")
    return jobs


# ── RSS Feeds ─────────────────────────────────────────────────────────────────

RSS_FEEDS = [
    {"name": "WWR Management",  "url": "https://weworkremotely.com/categories/remote-management-and-finance-jobs.rss", "filter": True},
    {"name": "Remote.co PM",    "url": "https://remote.co/remote-jobs/product-manager/feed/",                         "filter": False},
    {"name": "HackerNews Jobs", "url": "https://hnrss.org/jobs",                                                       "filter": True},
    {"name": "Remotive RSS",    "url": "https://remotive.com/remote-jobs/feed/product",                                "filter": True},
]


def fetch_rss(feed: dict) -> list[dict]:
    jobs = []
    try:
        parsed = feedparser.parse(feed["url"], agent=HEADERS["User-Agent"])
        if getattr(parsed, "status", 200) >= 400:
            print(f"  [RSS {getattr(parsed,'status','')}] {feed['name']}")
            return []
        for entry in parsed.entries:
            url = entry.get("link") or entry.get("id", "")
            if not url:
                continue
            title = (entry.get("title") or "Untitled").strip()
            if feed.get("filter") and not _is_pm_role(title):
                continue
            company = ""
            if " at " in title:
                company = title.rsplit(" at ", 1)[-1].strip()
            elif " — " in title:
                company = title.rsplit(" — ", 1)[-1].strip()
            elif " - " in title:
                company = title.rsplit(" - ", 1)[-1].strip()

            content = entry.get("content", [])
            if content and isinstance(content, list):
                description = _strip_html(content[0].get("value", ""))
            else:
                description = _strip_html(entry.get("summary", "") or entry.get("description", ""))

            jobs.append(_make_job(
                feed["name"],
                title,
                company or "Unknown",
                str(entry.get("location", "Remote")),
                url,
                description,
                entry.get("published") or entry.get("updated"),
            ))
    except Exception as e:
        print(f"  [RSS] {feed['name']}: {e}")
    return jobs


# ── JSearch (LinkedIn/Indeed via RapidAPI) ────────────────────────────────────

def fetch_jsearch(api_key: str) -> list[dict]:
    if not api_key:
        return []
    jobs = []
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={"query": "Senior Product Manager OR Product Manager remote", "page": "1", "num_results": "20", "date_posted": "week"},
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        for j in r.json().get("data", []):
            apply_url = j.get("job_apply_link") or j.get("job_google_link", "")
            if not apply_url:
                continue
            city = j.get("job_city", "")
            country = j.get("job_country", "")
            location = ", ".join(filter(None, [city, country])) or "Unknown"
            jobs.append(_make_job(
                j.get("job_publisher", "LinkedIn/Indeed"),
                j.get("job_title", ""),
                j.get("employer_name", "Unknown"),
                location,
                apply_url,
                j.get("job_description", ""),
                j.get("job_posted_at_datetime_utc"),
            ))
    except Exception as e:
        print(f"  [JSearch] {e}")
    return jobs


# ── Save ──────────────────────────────────────────────────────────────────────

def save_jobs(jobs: list[dict]) -> int:
    from db import db_ctx
    new_count = 0
    with db_ctx() as conn:
        for job in jobs:
            if not job.get("url"):
                continue
            try:
                conn.execute("""
                    INSERT INTO jobs
                        (id, source, title, company, location, url, description,
                         posted_at, fetched_at, status, seniority, yoe_required)
                    VALUES
                        (:id, :source, :title, :company, :location, :url, :description,
                         :posted_at, :fetched_at, 'new', :seniority, :yoe_required)
                """, job)
                new_count += 1
            except sqlite3.IntegrityError:
                pass
    return new_count


# ── Orchestrator ──────────────────────────────────────────────────────────────

def fetch_all(sources: dict = None, jsearch_key: str = "") -> int:
    cfg = sources or {}
    total = 0

    steps = [
        ("remotive_api",  "Remotive API",   fetch_remotive),
        ("remoteok_api",  "RemoteOK API",   fetch_remoteok),
        ("arbeitnow_api", "Arbeitnow API",  fetch_arbeitnow),
    ]
    for key, label, fn in steps:
        if cfg.get(key, True):
            print(f"  Fetching {label}...")
            jobs = fn()
            n = save_jobs(jobs)
            print(f"    {len(jobs)} found, {n} new")
            total += n

    rss_key_map = {
        "WWR Management":  "wwr_rss",
        "Remote.co PM":    "remoteco_rss",
        "HackerNews Jobs": "hn_rss",
        "Remotive RSS":    "remotive_rss",
    }
    for feed in RSS_FEEDS:
        config_key = rss_key_map.get(feed["name"], feed["name"])
        if not cfg.get(config_key, True):
            continue
        print(f"  Fetching {feed['name']} RSS...")
        jobs = fetch_rss(feed)
        n = save_jobs(jobs)
        print(f"    {len(jobs)} found, {n} new")
        total += n

    if cfg.get("jsearch_api", False) and jsearch_key:
        print("  Fetching JSearch (LinkedIn/Indeed)...")
        jobs = fetch_jsearch(jsearch_key)
        n = save_jobs(jobs)
        print(f"    {len(jobs)} found, {n} new")
        total += n

    return total
