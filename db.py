"""
Database layer — SQLite with WAL for safe concurrent reads.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# DATA_DIR lets Railway/Render/Fly point to a persistent volume.
# Falls back to the app directory for local development.
_data_dir = Path(os.environ.get("DATA_DIR", Path(__file__).parent))
_data_dir.mkdir(parents=True, exist_ok=True)
DB_PATH = _data_dir / "jobs.db"


def get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db_ctx():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    with db_ctx() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id           TEXT PRIMARY KEY,
                source       TEXT NOT NULL,
                title        TEXT NOT NULL,
                company      TEXT,
                location     TEXT,
                url          TEXT NOT NULL UNIQUE,
                description  TEXT,
                posted_at    TEXT,
                fetched_at   TEXT,
                status       TEXT DEFAULT 'new',
                fit_score    INTEGER,
                analysis_json TEXT,
                seniority    TEXT,
                yoe_required INTEGER,
                tailored_resume TEXT,
                cover_letter TEXT
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        db.execute("CREATE INDEX IF NOT EXISTS idx_status   ON jobs(status)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_seniority ON jobs(seniority)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_score    ON jobs(fit_score)")
        db.execute("CREATE INDEX IF NOT EXISTS idx_posted   ON jobs(posted_at)")


# ── Jobs ───────────────────────────────────────────────────────────────────────

def _row_to_dict(row) -> dict:
    d = dict(row)
    raw = d.pop("analysis_json", None)
    d["analysis"] = json.loads(raw) if raw else {}
    return d


def get_jobs(
    status: str = None,
    seniority: str = None,
    min_yoe: int = None,
    max_yoe: int = None,
    min_score: int = 0,
    limit: int = 60,
) -> list[dict]:
    clauses, params = [], []

    if status and status != "all":
        clauses.append("status = ?")
        params.append(status)

    if seniority and seniority != "all":
        clauses.append("seniority = ?")
        params.append(seniority)

    if min_yoe is not None and min_yoe > 0:
        clauses.append("(yoe_required IS NULL OR yoe_required >= ?)")
        params.append(min_yoe)

    if max_yoe is not None and max_yoe > 0:
        clauses.append("(yoe_required IS NULL OR yoe_required <= ?)")
        params.append(max_yoe)

    if min_score > 0:
        clauses.append("(fit_score IS NULL OR fit_score >= ?)")
        params.append(min_score)

    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    params.append(limit)

    with get_db() as db:
        rows = db.execute(
            f"""SELECT * FROM jobs {where}
                ORDER BY
                    CASE WHEN fit_score IS NULL THEN 1 ELSE 0 END,
                    fit_score DESC,
                    posted_at DESC
                LIMIT ?""",
            params,
        ).fetchall()

    return [_row_to_dict(r) for r in rows]


def get_job(job_id: str) -> Optional[dict]:
    with get_db() as db:
        row = db.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    return _row_to_dict(row) if row else None


def get_stats() -> dict:
    with get_db() as db:
        r = db.execute("""
            SELECT
                COUNT(CASE WHEN status = 'scored'  THEN 1 END) AS to_review,
                COUNT(CASE WHEN status = 'new'     THEN 1 END) AS unscored,
                COUNT(CASE WHEN status = 'applied' THEN 1 END) AS applied,
                COUNT(CASE WHEN status = 'maybe'   THEN 1 END) AS maybe,
                COUNT(CASE WHEN status = 'skipped' THEN 1 END) AS skipped,
                AVG(CASE WHEN status = 'scored' AND fit_score IS NOT NULL THEN fit_score END) AS avg_score
            FROM jobs
        """).fetchone()
        seniority_rows = db.execute("""
            SELECT seniority, COUNT(*) AS cnt
            FROM jobs WHERE status IN ('scored','new') AND seniority IS NOT NULL
            GROUP BY seniority
        """).fetchall()
    d = dict(r)
    d["seniority_counts"] = {row["seniority"]: row["cnt"] for row in seniority_rows}
    return d


def set_job_status(job_id: str, status: str):
    with db_ctx() as db:
        db.execute("UPDATE jobs SET status = ? WHERE id = ?", (status, job_id))


def save_analysis(job_id: str, score: int, analysis: dict, tailored_resume: str = None, cover_letter: str = None):
    with db_ctx() as db:
        db.execute("""
            UPDATE jobs SET
                fit_score    = ?,
                analysis_json = ?,
                status       = 'scored',
                tailored_resume = ?,
                cover_letter = ?
            WHERE id = ?
        """, (score, json.dumps(analysis), tailored_resume, cover_letter, job_id))


def save_prep(job_id: str, tailored_resume: str, cover_letter: str):
    with db_ctx() as db:
        db.execute(
            "UPDATE jobs SET tailored_resume = ?, cover_letter = ? WHERE id = ?",
            (tailored_resume, cover_letter, job_id),
        )


# ── Settings ───────────────────────────────────────────────────────────────────

def get_setting(key: str, default=None):
    with get_db() as db:
        row = db.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default


def set_setting(key: str, value: str):
    with db_ctx() as db:
        db.execute(
            "INSERT OR REPLACE INTO settings(key, value) VALUES (?, ?)",
            (key, value),
        )
