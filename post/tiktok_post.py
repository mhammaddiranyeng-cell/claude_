"""Upload a clip to TikTok via the official Content Posting API (v2).

Setup (one-time, you do this yourself at developers.tiktok.com):
  1. Create an app, request the "video.publish" scope.
  2. Complete the OAuth authorization-code flow for your own account to get
     an access_token + refresh_token; store them in .env.
  3. IMPORTANT: until TikTok audits your app, it can only post with
     privacy_level="SELF_ONLY" (visible only to you, not public). Public
     posting requires passing their app review -- there is no way around
     this from our side, it's enforced server-side by TikTok.

Access tokens expire in 24h; the refresh token lasts ~365 days. Every
call here refreshes first automatically, so you never need to re-run
tiktok_auth_helper.py just because time passed.

Docs: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""
import os

import requests
from dotenv import find_dotenv, set_key

API_BASE = "https://open.tiktokapis.com/v2"
TOKEN_URL = f"{API_BASE}/oauth/token/"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB, within TikTok's allowed chunk range


def _refresh_access_token() -> str:
    client_key = os.environ["TIKTOK_CLIENT_KEY"]
    client_secret = os.environ["TIKTOK_CLIENT_SECRET"]
    refresh_token = os.environ["TIKTOK_REFRESH_TOKEN"]

    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    data = resp.json() if resp.content else {}
    if not resp.ok or "access_token" not in data:
        raise RuntimeError(f"TikTok token refresh failed (HTTP {resp.status_code}): {data}")

    access_token = data["access_token"]
    new_refresh_token = data.get("refresh_token", refresh_token)

    # TikTok rotates the refresh token on each use -- persist both back to
    # .env so the next run (even days later) has a valid one to start from.
    dotenv_path = find_dotenv()
    if dotenv_path:
        set_key(dotenv_path, "TIKTOK_ACCESS_TOKEN", access_token)
        set_key(dotenv_path, "TIKTOK_REFRESH_TOKEN", new_refresh_token)
    os.environ["TIKTOK_ACCESS_TOKEN"] = access_token
    os.environ["TIKTOK_REFRESH_TOKEN"] = new_refresh_token

    return access_token


def upload_video(video_path: str, title: str, privacy_level: str = "SELF_ONLY") -> str:
    """Initiates + uploads a direct post. Returns the publish_id to poll for status."""
    access_token = _refresh_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    video_size = os.path.getsize(video_path)
    total_chunks = max(1, (video_size + CHUNK_SIZE - 1) // CHUNK_SIZE)

    init_body = {
        "post_info": {
            "title": title[:150],
            "privacy_level": privacy_level,
            "disable_duet": False,
            "disable_comment": False,
            "disable_stitch": False,
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": min(CHUNK_SIZE, video_size),
            "total_chunk_count": total_chunks,
        },
    }
    resp = requests.post(f"{API_BASE}/post/publish/video/init/", headers=headers, json=init_body)
    resp.raise_for_status()
    data = resp.json()["data"]
    publish_id, upload_url = data["publish_id"], data["upload_url"]

    with open(video_path, "rb") as f:
        offset = 0
        chunk_index = 0
        while offset < video_size:
            chunk = f.read(CHUNK_SIZE)
            chunk_end = offset + len(chunk) - 1
            put_headers = {
                "Content-Range": f"bytes {offset}-{chunk_end}/{video_size}",
                "Content-Type": "video/mp4",
            }
            put_resp = requests.put(upload_url, headers=put_headers, data=chunk)
            put_resp.raise_for_status()
            offset += len(chunk)
            chunk_index += 1

    return publish_id


def check_status(publish_id: str) -> dict:
    access_token = _refresh_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(
        f"{API_BASE}/post/publish/status/fetch/",
        headers=headers,
        json={"publish_id": publish_id},
    )
    resp.raise_for_status()
    return resp.json()["data"]
