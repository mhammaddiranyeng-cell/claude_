"""One-time local helper to get a TikTok access/refresh token pair.

Run this on your own machine (never in a remote/cloud session):

    python -m post.tiktok_auth_helper

It starts a tiny local server on http://localhost:8787/callback (must match
the redirect URI registered in your TikTok app's Login Kit settings), prints
a URL for you to open and approve in your browser, then prints the resulting
access_token / refresh_token for you to paste into your own .env. Nothing is
sent anywhere except TikTok's official OAuth endpoints.
"""
import base64
import hashlib
import http.server
import os
import secrets
import threading
import urllib.parse
import webbrowser

import requests
from dotenv import load_dotenv

REDIRECT_URI = "http://localhost:8787/callback"
AUTHORIZE_URL = "https://www.tiktok.com/v2/auth/authorize"
TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
SCOPE = "video.publish"

_result = {}


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        _result["code"] = params.get("code", [None])[0]
        _result["state"] = params.get("state", [None])[0]
        _result["error"] = params.get("error", [None])[0]

        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        body = "Done -- you can close this tab and go back to your terminal." \
            if _result.get("code") else f"Error: {_result.get('error')}"
        self.wfile.write(body.encode())

    def log_message(self, *args):
        pass  # keep the console quiet


def _make_pkce_pair():
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def main() -> None:
    load_dotenv()
    client_key = os.environ["TIKTOK_CLIENT_KEY"]
    client_secret = os.environ["TIKTOK_CLIENT_SECRET"]

    state = secrets.token_urlsafe(16)
    code_verifier, code_challenge = _make_pkce_pair()

    auth_params = {
        "client_key": client_key,
        "response_type": "code",
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URI,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTHORIZE_URL}?{urllib.parse.urlencode(auth_params)}"

    server = http.server.HTTPServer(("localhost", 8787), _CallbackHandler)
    thread = threading.Thread(target=server.handle_request)  # handles exactly one request
    thread.start()

    print("Opening your browser to approve access. If it doesn't open automatically, visit:\n")
    print(auth_url, "\n")
    webbrowser.open(auth_url)

    thread.join(timeout=300)
    server.server_close()

    if _result.get("error"):
        raise SystemExit(f"TikTok returned an error: {_result['error']}")
    if not _result.get("code"):
        raise SystemExit("Timed out waiting for the browser approval. Try again.")
    if _result.get("state") != state:
        raise SystemExit("State mismatch -- possible tampering, aborting.")

    token_resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": _result["code"],
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code_verifier": code_verifier,
        },
    )
    token_resp.raise_for_status()
    data = token_resp.json()

    print("\nSuccess. Add these to your local .env:\n")
    print(f"TIKTOK_ACCESS_TOKEN={data['access_token']}")
    print(f"TIKTOK_REFRESH_TOKEN={data['refresh_token']}")
    print(f"\n(access token expires in {data.get('expires_in')}s, "
          f"refresh token in {data.get('refresh_expires_in')}s)")


if __name__ == "__main__":
    main()
