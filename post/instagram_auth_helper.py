"""One-time local helper to get an Instagram Business Login access token.

Run this on your own machine (never in a remote/cloud session):

    python -m post.instagram_auth_helper

It starts a tiny local server on http://localhost:8788/callback (must
match the redirect URI registered in your app's "Instagram business
login" settings), prints a URL for you to open and approve in your
browser, exchanges the resulting code for a short-lived token, then
exchanges that for a long-lived (~60 day) token and prints it along
with your Instagram user ID for you to paste into your own .env.
"""
import http.server
import json
import os
import threading
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

REDIRECT_URI = "http://localhost:8788/callback"
AUTHORIZE_URL = "https://www.instagram.com/oauth/authorize"
SHORT_TOKEN_URL = "https://api.instagram.com/oauth/access_token"
LONG_TOKEN_URL = "https://graph.instagram.com/access_token"
ME_URL = "https://graph.instagram.com/me"
SCOPE = "instagram_business_basic,instagram_business_content_publish"

_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _result["code"] = params.get("code", [None])[0]
        _result["error"] = params.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = "Done -- you can close this tab and go back to your terminal." \
            if _result.get("code") else f"Error: {_result.get('error')}"
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass


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

    server = http.server.HTTPServer(("localhost", 8788), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print("Opening your browser to approve access. If it doesn't open automatically, visit:\n")
    print(auth_url, "\n")
    webbrowser.open(auth_url)

    thread.join(timeout=300)
    server.server_close()

    if _result.get("error"):
        raise SystemExit(f"Instagram returned an error: {_result['error']}")
    if not _result.get("code"):
        raise SystemExit("Timed out waiting for the browser approval. Try again.")

    short_resp = requests.post(
        SHORT_TOKEN_URL,
        data={
            "client_id": app_id,
            "client_secret": app_secret,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": _result["code"],
        },
    )
    short_resp.raise_for_status()
    short_data = short_resp.json()
    if "access_token" not in short_data:
        raise SystemExit(f"Short-lived token exchange failed: {short_data}")

    long_resp = requests.get(
        LONG_TOKEN_URL,
        params={
            "grant_type": "ig_exchange_token",
            "client_secret": app_secret,
            "access_token": short_data["access_token"],
        },
    )
    long_resp.raise_for_status()
    long_data = long_resp.json()
    if "access_token" not in long_data:
        raise SystemExit(f"Long-lived token exchange failed: {long_data}")

    access_token = long_data["access_token"]

    me_resp = requests.get(ME_URL, params={"fields": "id,username", "access_token": access_token})
    me_resp.raise_for_status()
    me_data = me_resp.json()

    print("\nSuccess. Add these to your local .env:\n")
    print(f"IG_ACCESS_TOKEN={access_token}")
    print(f"IG_USER_ID={me_data.get('id')}")
    print(f"\n(logged in as @{me_data.get('username')}, token expires in ~{long_data.get('expires_in', 0) // 86400} days)")


if __name__ == "__main__":
    main()
