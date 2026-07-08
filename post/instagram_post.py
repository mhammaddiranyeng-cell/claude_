"""Publish a Reel via the official Meta Graph API (Instagram Content Publishing).

Setup (one-time, you do this yourself):
  1. Your Instagram account must be a Business or Creator account.
  2. Create a Meta app at developers.facebook.com, add "Instagram Graph API".
  3. Get a long-lived access token with instagram_content_publish permission,
     and your IG Business Account ID. Store both in .env.
  4. Graph API requires the video to be reachable at a public URL (it fetches
     it server-side) -- it does not accept raw file bytes. Host the rendered
     clip somewhere reachable (e.g. a private S3/GCS bucket with a signed
     URL, or any temporary file host) and pass that URL in.

Docs: https://developers.facebook.com/docs/instagram-platform/content-publishing
"""
import os
import time

import requests

API_BASE = "https://graph.facebook.com/v19.0"


def publish_reel(video_url: str, caption: str, poll_interval: float = 5.0, timeout: float = 600.0) -> str:
    ig_user_id = os.environ["IG_BUSINESS_ACCOUNT_ID"]
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
    create_resp.raise_for_status()
    creation_id = create_resp.json()["id"]

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status_resp = requests.get(
            f"{API_BASE}/{creation_id}",
            params={"fields": "status_code", "access_token": access_token},
        )
        status_resp.raise_for_status()
        status_code = status_resp.json().get("status_code")
        if status_code == "FINISHED":
            break
        if status_code == "ERROR":
            raise RuntimeError(f"Instagram failed to process container {creation_id}")
        time.sleep(poll_interval)
    else:
        raise TimeoutError(f"Instagram container {creation_id} did not finish processing in time")

    publish_resp = requests.post(
        f"{API_BASE}/{ig_user_id}/media_publish",
        data={"creation_id": creation_id, "access_token": access_token},
    )
    publish_resp.raise_for_status()
    return publish_resp.json()["id"]


def get_permalink(media_id: str) -> str:
    access_token = os.environ["IG_ACCESS_TOKEN"]
    resp = requests.get(
        f"{API_BASE}/{media_id}",
        params={"fields": "permalink", "access_token": access_token},
    )
    resp.raise_for_status()
    return resp.json()["permalink"]
