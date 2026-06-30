#!/usr/bin/env python3
"""
Entry point:
  python run.py serve    — start the dashboard at http://localhost:8000
  python run.py refresh  — fetch + score jobs (no web server)
"""

import sys


def serve():
    import uvicorn
    print("PM Dashboard → http://localhost:8000")
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)


def refresh():
    import os
    import json
    from dotenv import load_dotenv
    load_dotenv()
    import db
    import fetcher
    import ai_engine
    from config import DEFAULT_SOURCES, SCORE_BATCH_SIZE

    db.init_db()
    sources = json.loads(db.get_setting("sources") or json.dumps(DEFAULT_SOURCES))
    jsearch_key = db.get_setting("jsearch_key") or os.environ.get("JSEARCH_API_KEY", "")

    print("Fetching jobs...")
    new = fetcher.fetch_all(sources, jsearch_key)
    print(f"\nFetched {new} new jobs")

    if os.environ.get("ANTHROPIC_API_KEY"):
        print("\nScoring with Claude...")
        scored = ai_engine.score_unscored(limit=SCORE_BATCH_SIZE)
        print(f"\nScored {scored} jobs")
    else:
        print("\nSet ANTHROPIC_API_KEY to score jobs")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "serve"
    if cmd == "refresh":
        refresh()
    else:
        serve()
