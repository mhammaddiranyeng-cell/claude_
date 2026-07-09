"""One-time local helper to get an Instagram Business Login access token.

Run this on your own machine (never in a remote/cloud session):

    python -m post.instagram_auth_helper

Instagram Business Login requires an HTTPS redirect URI (no plain
http://localhost exception), so this routes through a static callback
page hosted on GitHub Pages (docs/instagram_callback.html) instead of
running a local server: it prints a URL for you to open and approve in
your browser, that page displays the resulting code, and you paste it
back here. Everything after that (token exchange, long-lived exchange,
looking up your user ID) is automatic.
"""
import os
import urllib.parse

import requests
from dotenv import load_dotenv

REDIRECT_URI = "https://mhammaddiranyeng-cell.github.io/claude_/instagram_callback.html"
AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
SHORT_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
ME_URL = "https://graph.instagram.com/me"
SCOPE = "instagram_business_basic,instagram_business_content_publish"


def main() -> None:
    load_dotenv()
    app_id = os.environ["IG_APP_ID"]
    app_secret = os.environ["IG_APP_SECRET"]

    auth_params = {
        "client_id": app_id,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPE,
        "response_type": "code",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(auth_params)}"

    print("Open this URL, log in, and approve access:\n")
    print(auth_url, "\n")
    print("You'll land on a page showing a code -- copy it and paste it below.")
    code = input("Code: ").strip()
    # Instagram sometimes appends a "#_" fragment to the code; strip it if present.
    code = code.split("#")[0]

    short_resp = requests.post(
        SHORT_TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    short_data = short_resp.json() if short_resp.content else {}
    if not short_resp.ok or "access_token" not in short_data:
        raise SystemExit(f"Short-lived token exchange failed (HTTP {short_resp.status_code}): {short_data}")

    long_resp = requests.get(
        LONG_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_data["access_token"],
        },
    )
    long_data = long_resp.json() if long_resp.content else {}
    if not long_resp.ok or "access_token" not in long_data:
        raise SystemExit(f"Long-lived token exchange failed (HTTP {long_resp.status_code}): {long_data}")

    access_token = long_data["access_token"]

    me_resp = requests.get(ME_URL, params={"fields": "id,username", "access_token": access_token})
    me_data = me_resp.json() if me_resp.content else {}
    if not me_resp.ok:
        raise SystemExit(f"Lookup of your Instagram user ID failed (HTTP {me_resp.status_code}): {me_data}")

    print("\nSuccess. Add these to your local .env:\n")
    print(f"IG_ACCESS_TOKEN={access_token}")
    print(f"IG_USER_ID={me_data.get('id')}")
    print(f"\n(logged in as @{me_data.get('username')}, token expires in ~{long_data.get('expires_in', 0) // 86400} days)")


if __name__ == "__main__":
    main()
