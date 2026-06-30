"""
PM Dashboard — Configuration defaults (overridden by DB settings at runtime)
"""

USER_PROFILE = {
    "name": "",
    "current_title": "Senior Product Manager",
    "years_experience": 5,
    "linkedin_url": "",
    "skills": [],
    "target_roles": ["Senior Product Manager", "Product Manager", "Lead PM", "Principal PM"],
    "preferred_locations": ["Remote"],
    "salary_range": {"min": 0, "max": 0, "currency": "USD"},
    "preferred_industries": [],
    "work_preference": "remote",
    "deal_breakers": [],
    "priorities": [],
}

PAGE_SIZE = 60
SCORE_BATCH_SIZE = 20
MIN_SCORE_THRESHOLD = 40

DEFAULT_SOURCES = {
    "remotive_api": True,
    "remoteok_api": True,
    "arbeitnow_api": True,
    "wwr_rss": True,
    "remoteco_rss": True,
    "hn_rss": True,
    "jsearch_api": False,
}
