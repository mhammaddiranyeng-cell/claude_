"""Post reviewed clip(s) from a manifest.json to one or more platforms.

You review the clips yourself first, then trigger posting. This does not
touch ContentRewards/Whop/Vyro at all; submit the resulting post URL(s)
there yourself -- see posted_urls.txt (written alongside the manifest)
for a ready-to-paste list.

Usage:
    python -m post.scheduler --manifest output/manifest.json --index 1 --platforms youtube,tiktok
    python -m post.scheduler --manifest output/manifest.json --all --platforms youtube --public
"""
import argparse
import json
import os
import time

from dotenv import load_dotenv
from googleapiclient.errors import HttpError

from . import youtube_post, tiktok_post, instagram_post, gcs_upload


def post_one(clip: dict, platforms: list, public: bool, instagram_video_url: str = None) -> list:
    """Returns a list of (platform, url_or_note) tuples for whatever was posted.

    Each platform is attempted independently -- one platform failing (e.g.
    a TikTok API error) no longer skips the remaining ones for this clip.
    """
    results = []

    if "youtube" in platforms:
        try:
            privacy = "public" if public else "private"
            video_id = youtube_post.upload_short(
                clip["clip"], title=clip["suggested_caption"][:100], description=clip["suggested_caption"],
                privacy_status=privacy,
            )
            url = f"https://youtube.com/watch?v={video_id}"
            print(f"  YouTube: uploaded as {privacy}, {url}")
            results.append(("youtube", url))
        except Exception as e:
            print(f"  YouTube: failed, {e}")

    if "tiktok" in platforms:
        try:
            publish_id = tiktok_post.upload_video(clip["clip"], title=clip["suggested_caption"])
            note = f"publish_id={publish_id} (TikTok's API doesn't return a post URL -- check your profile)"
            print(f"  TikTok: submitted, {note}")
            results.append(("tiktok", note))
        except Exception as e:
            print(f"  TikTok: failed, {e}")

    if "instagram" in platforms:
        try:
            video_url = instagram_video_url
            if not video_url:
                print("  Instagram: uploading clip to Google Cloud Storage for a temporary public URL ...")
                video_url = gcs_upload.upload_and_sign(clip["clip"])
            media_id = instagram_post.publish_reel(video_url, caption=clip["suggested_caption"])
            permalink = instagram_post.get_permalink(media_id)
            print(f"  Instagram: published, {permalink}")
            results.append(("instagram", permalink))
        except Exception as e:
            print(f"  Instagram: failed, {e}")

    return results


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Post reviewed clip(s) to social platforms.")
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--index", type=int, help="1-based clip index from the manifest.")
    parser.add_argument("--all", action="store_true", help="Post every clip in the manifest.")
    parser.add_argument("--platforms", required=True, help="Comma-separated: youtube,tiktok,instagram")
    parser.add_argument("--public", action="store_true", help="Upload YouTube videos as public directly instead of private-for-review.")
    parser.add_argument("--instagram-video-url", help="Override: use this exact public URL instead of auto-uploading each clip to GCS (only makes sense with a single clip, not --all).")
    parser.add_argument("--delay", type=float, default=5.0, help="Seconds to wait between clips with --all.")
    args = parser.parse_args()

    if not args.all and args.index is None:
        raise SystemExit("Pass either --index N or --all.")

    with open(args.manifest) as f:
        manifest = json.load(f)

    output_dir = os.path.dirname(os.path.abspath(args.manifest))
    urls_path = os.path.join(output_dir, "posted_urls.txt")

    indices = range(len(manifest)) if args.all else [args.index - 1]
    platforms = [p.strip().lower() for p in args.platforms.split(",")]

    with open(urls_path, "a") as urls_file:
        for i, clip_idx in enumerate(indices):
            clip = manifest[clip_idx]
            print(f"[{clip_idx + 1}/{len(manifest)}] Posting {clip['clip']} ...")
            try:
                results = post_one(clip, platforms, args.public, args.instagram_video_url)
                for platform, url in results:
                    urls_file.write(f"{clip['clip']}\t{platform}\t{url}\n")
                urls_file.flush()
            except HttpError as e:
                if e.resp.status == 403 and ("quota" in str(e).lower() or "dailyLimit" in str(e)):
                    print(f"  YouTube daily upload quota hit -- stopping here. Try the rest again after quota resets (~midnight Pacific).")
                    break
                print(f"  Failed: {e}")
            except Exception as e:
                print(f"  Failed: {e}")

            if args.all and i < len(indices) - 1:
                time.sleep(args.delay)

    print(f"\nPosted URLs logged to {urls_path}")


if __name__ == "__main__":
    main()
