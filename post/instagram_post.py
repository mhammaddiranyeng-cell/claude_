"""Publish a Reel via the Instagram API with Instagram Login (graph.instagram.com).

Setup (one-time, you do this yourself):
  1. Your Instagram account must be a Business or Creator account.
  2. Create a Meta app at developers.facebook.com, add the "Instagram API"
     product (the Instagram-Login-based one, not the Facebook-Page-based
     "API setup with Facebook login" variant).
  3. Add yourself as an "Instagram Tester" under that product's Roles tab,
     and accept the invite from within the Instagram app.
  4. Request `instagram_business_content_publish` under Permissions and
     features (usually "Ready for testing" with no review needed for
     tester accounts).
  5. Run `python -m post.instagram_auth_helper` to get IG_ACCESS_TOKEN and
     IG_USER_ID -- see that module for the redirect URI it needs registered.
  6. This API requires the video to be reachable at a public URL (it
     fetches it server-side) -- it does not accept raw file bytes.
     scheduler.py handles this automatically via ngrok_tunnel.py.

Docs: https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login
"""
import os
import time

import requests

API_BASE = "https://graph.instagram.com"


def _check(resp: requests.Response) -> dict:
    data = resp.json() if resp.content else {}
    if not resp.ok:
        raise RuntimeError(f"Instagram API error (HTTP {resp.status_code}): {data}")
    return data


def publish_reel(video_url: str, caption: str, poll_interval: float = 5.0, timeout: float = 600.0) -> str:
    ig_user_id = os.environ["IG_USER_ID"]
    access_token = os.environ["IG_ACCESS_TOKEN"]

    create_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media",
        data={
            "media_type": "REELS",
            "video_url": video_url,
            "caption": caption,
            "access_token": access_token,
        },
    )
    creation_id = _check(create_resp)["id"]

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_resp = requests.get(
            f"{API_BASE}/{creation_id}",
            params={"fields": "status_code,status", "access_token": access_token},
        )
        status_data = _check(status_resp)
        status_code = status_data.get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram failed to process container {creation_id}: {status_data}")
        time.sleep(poll_interval)
    else:
        raise TimeoutError(f"Instagram container {creation_id} did not finish processing in time")

    publish_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
    )
    return _check(publish_resp)["id"]


def get_permalink(media_id: str) -> str:
    access_token = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.get(
        f"{API_BASE}/{media_id}",
        params={"fields": "permalink", "access_token": access_token},
    )
    return _check(resp)["permalink"]
