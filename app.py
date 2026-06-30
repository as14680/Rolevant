"""
PM Dashboard — FastAPI server
"""

import json
import os
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel

load_dotenv()

import db
import fetcher
import ai_engine
from config import USER_PROFILE, DEFAULT_SOURCES, PAGE_SIZE, SCORE_BATCH_SIZE

app = FastAPI(title="Rolevant")
STATIC = Path(__file__).parent / "static"


@app.on_event("startup")
def startup():
    db.init_db()


# ── Serve UI ──────────────────────────────────────────────────────────────────

@app.get("/")
def serve_ui():
    return FileResponse(STATIC / "index.html")


# ── Stats ─────────────────────────────────────────────────────────────────────

@app.get("/api/stats")
def get_stats():
    return db.get_stats()


# ── Jobs ──────────────────────────────────────────────────────────────────────

@app.get("/api/jobs")
def list_jobs(
    status: str = "scored",
    seniority: str = "all",
    min_yoe: int = 0,
    max_yoe: int = 0,
    min_score: int = 0,
    limit: int = PAGE_SIZE,
):
    return db.get_jobs(
        status=status,
        seniority=None if seniority == "all" else seniority,
        min_yoe=min_yoe if min_yoe > 0 else None,
        max_yoe=max_yoe if max_yoe > 0 else None,
        min_score=min_score,
        limit=limit,
    )


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")
    return job


# ── Actions ───────────────────────────────────────────────────────────────────

STATUS_MAP = {"apply": "applied", "skip": "skipped", "maybe": "maybe", "reset": "scored"}


class ActionPayload(BaseModel):
    action: str


@app.post("/api/jobs/{job_id}/action")
def job_action(job_id: str, payload: ActionPayload):
    if payload.action not in STATUS_MAP:
        raise HTTPException(400, f"Unknown action: {payload.action}")
    db.set_job_status(job_id, STATUS_MAP[payload.action])
    return {"status": "ok", "new_status": STATUS_MAP[payload.action]}


# ── One-click Prep ────────────────────────────────────────────────────────────

@app.post("/api/jobs/{job_id}/prep")
def prep_job(job_id: str):
    job = db.get_job(job_id)
    if not job:
        raise HTTPException(404, "Job not found")

    # Return cached prep if available
    if job.get("tailored_resume") and job.get("cover_letter"):
        return {
            "tailored_resume": job["tailored_resume"],
            "cover_letter": job["cover_letter"],
            "job_url": job["url"],
            "cached": True,
        }

    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY not set")

    tailored, cover = ai_engine.generate_prep(job)
    if tailored or cover:
        db.save_prep(job_id, tailored, cover)

    return {
        "tailored_resume": tailored,
        "cover_letter": cover,
        "job_url": job["url"],
        "cached": False,
    }


# ── Settings ──────────────────────────────────────────────────────────────────

@app.get("/api/settings")
def get_settings():
    profile_raw = db.get_setting("profile")
    profile = json.loads(profile_raw) if profile_raw else USER_PROFILE
    return {
        "profile": profile,
        "resume": db.get_setting("resume") or "",
        "sources": json.loads(db.get_setting("sources") or json.dumps(DEFAULT_SOURCES)),
        "jsearch_key": db.get_setting("jsearch_key") or "",
    }


class SettingsPayload(BaseModel):
    profile: Optional[dict] = None
    resume: Optional[str] = None
    sources: Optional[dict] = None
    jsearch_key: Optional[str] = None


@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    if payload.profile is not None:
        db.set_setting("profile", json.dumps(payload.profile))
    if payload.resume is not None:
        db.set_setting("resume", payload.resume)
    if payload.sources is not None:
        db.set_setting("sources", json.dumps(payload.sources))
    if payload.jsearch_key is not None:
        db.set_setting("jsearch_key", payload.jsearch_key)
    return {"status": "ok"}


# ── Refresh ───────────────────────────────────────────────────────────────────

@app.post("/api/refresh")
def refresh():
    import traceback
    sources = json.loads(db.get_setting("sources") or json.dumps(DEFAULT_SOURCES))
    jsearch_key = db.get_setting("jsearch_key") or os.environ.get("JSEARCH_API_KEY", "")
    errors = []

    try:
        new_jobs = fetcher.fetch_all(sources, jsearch_key)
    except Exception as e:
        traceback.print_exc()
        errors.append(f"fetch: {e}")
        new_jobs = 0

    try:
        if not os.environ.get("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY not set — skipping scoring")
        scored = ai_engine.score_unscored(limit=SCORE_BATCH_SIZE)
    except Exception as e:
        traceback.print_exc()
        errors.append(f"score: {e}")
        scored = 0

    result = {"new_jobs": new_jobs, "scored": scored}
    if errors:
        result["errors"] = errors
    return result


@app.post("/api/score-pending")
def score_pending():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise HTTPException(400, "ANTHROPIC_API_KEY not set")
    try:
        scored = ai_engine.score_unscored(limit=SCORE_BATCH_SIZE)
        return {"scored": scored}
    except Exception as e:
        raise HTTPException(500, str(e))
