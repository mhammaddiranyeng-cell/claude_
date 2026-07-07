"""Post one reviewed clip from a manifest.json to one or more platforms.

This is intentionally a manual, one-clip-at-a-time CLI -- you review the
clip and caption yourself, then trigger the post. It does not touch
ContentRewards/Whop at all; submit the resulting post URL there yourself.

Usage:
    python -m post.scheduler --manifest output/manifest.json --index 1 --platforms youtube,tiktok
"""
import argparse
import json

from dotenv import load_dotenv

from . import youtube_post, tiktok_post, instagram_post


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Post a reviewed clip to social platforms.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--index", type=int, required=True, help="1-based clip index from the manifest.")
    parser.add_argument("--platforms", required=True, help="Comma-separated: youtube,tiktok,instagram")
    parser.add_argument("--instagram-video-url", help="Public URL for the clip (required if posting to instagram).")
    args = parser.parse_args()

    with open(args.manifest) as f:
        manifest = json.load(f)
    clip = manifest[args.index - 1]

    platforms = [p.strip().lower() for p in args.platforms.split(",")]

    if "youtube" in platforms:
        video_id = youtube_post.upload_short(
            clip["clip"], title=clip["suggested_caption"][:100], description=clip["suggested_caption"],
        )
        print(f"YouTube: uploaded as private, id={video_id}. Review then flip to public in Studio or via API.")

    if "tiktok" in platforms:
        publish_id = tiktok_post.upload_video(clip["clip"], title=clip["suggested_caption"])
        print(f"TikTok: submitted, publish_id={publish_id}. Check post/tiktok_post.check_status(publish_id).")

    if "instagram" in platforms:
        if not args.instagram_video_url:
            raise SystemExit("--instagram-video-url is required to post to Instagram (Graph API needs a public URL).")
        media_id = instagram_post.publish_reel(args.instagram_video_url, caption=clip["suggested_caption"])
        print(f"Instagram: published, media_id={media_id}")


if __name__ == "__main__":
    main()
