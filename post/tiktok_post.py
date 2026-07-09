"""Upload a clip to TikTok via the official Content Posting API (v2).

Setup (one-time, you do this yourself at developers.tiktok.com):
  1. Create an app, request the "video.publish" scope.
  2. Complete the OAuth authorization-code flow for your own account to get
     an access_token + refresh_token; store them in .env.
  3. IMPORTANT: until TikTok audits your app, it can only post with
     privacy_level="SELF_ONLY" (visible only to you, not public). Public
     posting requires passing their app review -- there is no way around
     this from our side, it's enforced server-side by TikTok.

Rather than hardcoding "SELF_ONLY" and needing a code change the day the
audit passes, upload_video() asks TikTok itself (creator_info/query) which
privacy levels the account is currently allowed to post with, and picks the
most public one available. Pre-audit that'll resolve to SELF_ONLY; the same
day TikTok approves the app, it starts resolving to PUBLIC_TO_EVERYONE with
no changes needed here.

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

# Most-public-first; used to pick the best option creator_info/query allows.
_PRIVACY_PREFERENCE = ["PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR", "SELF_ONLY"]


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


def get_creator_info(access_token: str) -> dict:
    """Returns TikTok's current rules for this account: allowed privacy
    levels, max duration, disabled interactions, etc. This can change
    (e.g. the day an app review is approved), so it's queried fresh on
    every upload rather than assumed."""
    resp = requests.post(
        f"{API_BASE}/post/publish/creator_info/query/",
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json={},
    )
    data = resp.json() if resp.content else {}
    if not resp.ok or "data" not in data:
        raise RuntimeError(f"TikTok creator_info query failed (HTTP {resp.status_code}): {data}")
    return data["data"]


def _pick_privacy_level(options: list) -> str:
    for level in _PRIVACY_PREFERENCE:
        if level in options:
            return level
    return options[0] if options else "SELF_ONLY"


def _init_post(headers: dict, title: str, privacy_level: str, video_size: int, chunk_size: int, total_chunks: int):
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
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunks,
        },
    }
    resp = requests.post(f"{API_BASE}/post/publish/video/init/", headers=headers, json=init_body)
    resp_data = resp.json() if resp.content else {}
    return resp, resp_data


def upload_video(video_path: str, title: str, privacy_level: str = None) -> str:
    """Initiates + uploads a direct post. Returns the publish_id to poll for status.

    If privacy_level isn't given, it's auto-picked from whatever TikTok's
    creator_info/query says this account can currently post with (the most
    public option available) -- see module docstring. Note that
    privacy_level_options reflects the ACCOUNT's own settings, not whether
    the APP has passed audit -- an unaudited app can still reject anything
    but SELF_ONLY even if creator_info offered a more public option, so we
    also catch that specific rejection below and fall back automatically.
    """
    access_token = _refresh_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    if privacy_level is None:
        creator_info = get_creator_info(access_token)
        options = creator_info.get("privacy_level_options", ["SELF_ONLY"])
        privacy_level = _pick_privacy_level(options)
        print(f"  TikTok: posting with privacy_level={privacy_level} (account's current options: {options})")

    video_size = os.path.getsize(video_path)

    # TikTok's rule: total_chunk_count = video_size // chunk_size (floor),
    # and the LAST chunk absorbs all remaining bytes (can exceed chunk_size,
    # up to 128MB) rather than trailing off as its own small final chunk.
    if video_size < 5 * 1024 * 1024:
        chunk_size = video_size
        total_chunks = 1
    else:
        chunk_size = CHUNK_SIZE
        total_chunks = max(1, video_size // chunk_size)

    resp, resp_data = _init_post(headers, title, privacy_level, video_size, chunk_size, total_chunks)
    if not resp.ok and resp_data.get("error", {}).get("code") == "unaudited_client_can_only_post_to_private_accounts" \
            and privacy_level != "SELF_ONLY":
        print(f"  TikTok: app isn't audited yet, {privacy_level} was rejected server-side -- falling back to SELF_ONLY for this post")
        privacy_level = "SELF_ONLY"
        resp, resp_data = _init_post(headers, title, privacy_level, video_size, chunk_size, total_chunks)

    if not resp.ok or "data" not in resp_data:
        raise RuntimeError(f"TikTok init failed (HTTP {resp.status_code}): {resp_data}")
    data = resp_data["data"]
    publish_id, upload_url = data["publish_id"], data["upload_url"]

    with open(video_path, "rb") as f:
        offset = 0
        for i in range(total_chunks):
            is_last = i == total_chunks - 1
            chunk = f.read() if is_last else f.read(chunk_size)
            chunk_end = offset + len(chunk) - 1
            put_headers = {
                "Content-Range": f"bytes {offset}-{chunk_end}/{video_size}",
                "Content-Type": "video/mp4",
            }
            put_resp = requests.put(upload_url, headers=put_headers, data=chunk)
            if not put_resp.ok:
                raise RuntimeError(f"TikTok chunk upload failed (HTTP {put_resp.status_code}): {put_resp.text}")
            offset += len(chunk)

    return publish_id


def check_status(publish_id: str) -> dict:
    access_token = _refresh_access_token()
    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}
    resp = requests.post(
        f"{API_BASE}/post/publish/status/fetch/",
        headers=headers,
        json={"publish_id": publish_id},
    )
    resp_data = resp.json() if resp.content else {}
    if not resp.ok or "data" not in resp_data:
        raise RuntimeError(f"TikTok status check failed (HTTP {resp.status_code}): {resp_data}")
    return resp_data["data"]
