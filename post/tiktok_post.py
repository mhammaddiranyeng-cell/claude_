"""Upload a clip to TikTok via the official Content Posting API (v2).

Setup (one-time, you do this yourself at developers.tiktok.com):
  1. Create an app, request the "video.publish" scope.
  2. Complete the OAuth authorization-code flow for your own account to get
     an access_token + refresh_token; store them in .env.
  3. IMPORTANT: until TikTok audits your app, it can only post with
     privacy_level="SELF_ONLY" (visible only to you, not public). Public
     posting requires passing their app review -- there is no way around
     this from our side, it's enforced server-side by TikTok.

Docs: https://developers.tiktok.com/doc/content-posting-api-reference-direct-post
"""
import os

import requests

API_BASE = "https://open.tiktokapis.com/v2"
CHUNK_SIZE = 10 * 1024 * 1024  # 10MB, within TikTok's allowed chunk range


def upload_video(video_path: str, title: str, privacy_level: str = "SELF_ONLY") -> str:
    """Initiates + uploads a direct post. Returns the publish_id to poll for status."""
    access_token = os.environ["TIKTOK_ACCESS_TOKEN"]
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
    access_token = os.environ["TIKTOK_ACCESS_TOKEN"]
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(
        f"{API_BASE}/post/publish/status/fetch/",
        headers=headers,
        json={"publish_id": publish_id},
    )
    resp.raise_for_status()
    return resp.json()["data"]
