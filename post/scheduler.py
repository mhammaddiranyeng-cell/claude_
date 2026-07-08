"""Post reviewed clip(s) from a manifest.json to one or more platforms.

You review the clips yourself first, then trigger posting. This does not
touch ContentRewards/Whop at all; submit the resulting post URL(s) there
yourself.

Usage:
    python -m post.scheduler --manifest output/manifest.json --index 1 --platforms youtube,tiktok
    python -m post.scheduler --manifest output/manifest.json --all --platforms youtube
"""
import argparse
import json
import time

from dotenv import load_dotenv
from googleapiclient.errors import HttpError

from . import youtube_post, tiktok_post, instagram_post


def post_one(clip: dict, platforms: list, instagram_video_url: str = None) -> None:
    if "youtube" in platforms:
        video_id = youtube_post.upload_short(
            clip["clip"], title=clip["suggested_caption"][:100], description=clip["suggested_caption"],
        )
        print(f"  YouTube: uploaded as private, id={video_id}. Review then flip to public in Studio or via API.")

    if "tiktok" in platforms:
        publish_id = tiktok_post.upload_video(clip["clip"], title=clip["suggested_caption"])
        print(f"  TikTok: submitted, publish_id={publish_id}. Check post/tiktok_post.check_status(publish_id).")

    if "instagram" in platforms:
        if not instagram_video_url:
            raise SystemExit("--instagram-video-url is required to post to Instagram (Graph API needs a public URL).")
        media_id = instagram_post.publish_reel(instagram_video_url, caption=clip["suggested_caption"])
        print(f"  Instagram: published, media_id={media_id}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Post reviewed clip(s) to social platforms.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--index", type=int, help="1-based clip index from the manifest.")
    parser.add_argument("--all", action="store_true", help="Post every clip in the manifest.")
    parser.add_argument("--platforms", required=True, help="Comma-separated: youtube,tiktok,instagram")
    parser.add_argument("--instagram-video-url", help="Public URL for the clip (required if posting to instagram; same URL used for every clip with --all, which only makes sense for a single clip).")
    parser.add_argument("--delay", type=float, default=5.0, help="Seconds to wait between clips with --all.")
    args = parser.parse_args()

    if not args.all and args.index is None:
        raise SystemExit("Pass either --index N or --all.")

    with open(args.manifest) as f:
        manifest = json.load(f)

    indices = range(len(manifest)) if args.all else [args.index - 1]
    platforms = [p.strip().lower() for p in args.platforms.split(",")]

    for i, clip_idx in enumerate(indices):
        clip = manifest[clip_idx]
        print(f"[{clip_idx + 1}/{len(manifest)}] Posting {clip['clip']} ...")
        try:
            post_one(clip, platforms, args.instagram_video_url)
        except HttpError as e:
            if e.resp.status == 403 and ("quota" in str(e).lower() or "dailyLimit" in str(e)):
                print(f"  YouTube daily upload quota hit -- stopping here. Try the rest again after quota resets (~midnight Pacific).")
                break
            print(f"  Failed: {e}")
        except Exception as e:
            print(f"  Failed: {e}")

        if args.all and i < len(indices) - 1:
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
