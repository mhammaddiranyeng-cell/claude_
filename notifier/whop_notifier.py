"""Alert you to new/matching ContentRewards campaigns -- does NOT join or submit anything.

Deliberately does not automate login, campaign joining, or submission on
contentrewards.com: that's the part of their bot-detection ("behavioral
patterns") most likely to get an account flagged, and it's a one-click
action anyway, so a human should keep doing it.

Two ways to get campaign data, in order of preference:

1. Whop's official REST API (docs.whop.com). Content Rewards runs on Whop,
   and Whop publishes a documented REST API + SDK. If it exposes an
   endpoint for listing content-rewards campaigns visible to your account,
   that is the correct, ToS-safe way to build this -- no scraping at all.
   WHOP_LIST_CAMPAIGNS_ENDPOINT below is a placeholder: the docs page was
   not reachable to confirm the exact path/shape, so verify it against
   docs.whop.com/api-reference (with your WHOP_API_KEY) before relying on it.

2. Fallback: poll the public /discover page's HTML for campaign titles and
   diff against the last-seen snapshot. This is best-effort -- the site
   sits behind Cloudflare bot protection, so this may get blocked or break
   whenever their frontend markup changes. Treat failures as "go check
   manually," not as a bug to route around aggressively (retrying harder
   against anti-bot protection is exactly the "behavioral pattern" that
   gets flagged).
"""
import json
import os
import re
from typing import List, Set

import requests

DISCOVER_URL = "https://contentrewards.com/discover"
STATE_FILE = os.path.join(os.path.dirname(__file__), ".seen_campaigns.json")

# TODO: verify against docs.whop.com/api-reference before use.
WHOP_API_BASE = "https://api.whop.com/api/v2"
WHOP_LIST_CAMPAIGNS_ENDPOINT = f"{WHOP_API_BASE}/content_rewards/campaigns"


def list_campaigns_via_whop_api() -> list:
    """Placeholder for the official-API path. Confirm the endpoint first."""
    api_key = os.environ["WHOP_API_KEY"]
    resp = requests.get(
        WHOP_LIST_CAMPAIGNS_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    resp.raise_for_status()
    return resp.json()


def _load_seen() -> Set[str]:
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return set(json.load(f))
    return set()


def _save_seen(seen: Set[str]) -> None:
    with open(STATE_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def check_discover_page_for_new_campaigns(keywords: List[str] = None) -> List[str]:
    """Best-effort HTML poll of the public discover page. Returns newly-seen titles."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; personal-campaign-checker/1.0)"}
    resp = requests.get(DISCOVER_URL, headers=headers, timeout=15)
    resp.raise_for_status()

    # Very rough title extraction -- the page is a JS-rendered SPA, so this
    # regex heuristic over the raw HTML may miss campaigns or need updating
    # whenever their markup changes.
    candidates = set(re.findall(r'"title"\s*:\s*"([^"]{3,120})"', resp.text))

    if keywords:
        lowered = [k.lower() for k in keywords]
        candidates = {c for c in candidates if any(k in c.lower() for k in lowered)}

    seen = _load_seen()
    new = sorted(candidates - seen)
    _save_seen(seen | candidates)
    return new


if __name__ == "__main__":
    new_campaigns = check_discover_page_for_new_campaigns()
    if new_campaigns:
        print("New campaigns since last check:")
        for title in new_campaigns:
            print(f"  - {title}")
        print("Go review + join manually at https://contentrewards.com/discover")
    else:
        print("No new campaigns found (or page structure didn't match -- verify manually).")
