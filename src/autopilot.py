"""Fully unattended: drop a video path + a description in at the terminal
prompt, and it edits AND posts every resulting clip with no review step.

Usage:
    python -m src.autopilot --config config.yaml
    python -m src.autopilot --config config.yaml --platforms youtube,tiktok --private

Unlike src/pipeline.py + post/scheduler.py run separately (which stop after
editing so you can review clips first), this chains straight through to
posting. Use the two-step flow instead if you want to check clips before
they go out.
"""
import argparse
import json
import os

from dotenv import load_dotenv

from .pipeline import run as run_pipeline
from post.scheduler import post_one


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Unattended edit-and-post: drop a video in, it posts itself.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--platforms", default="youtube,tiktok,instagram")
    parser.add_argument("--private", action="store_true", help="Upload YouTube as private instead of public.")
    args = parser.parse_args()

    video_path = input("Drop the video file path here: ").strip().strip("'\"")
    if not os.path.isfile(video_path):
        raise SystemExit(f"No such file: {video_path}")

    description = input(
        "Describe what's in this video (used to pick editing style + hashtags; "
        "leave blank to use config.yaml's default): "
    ).strip()

    manifest_path = run_pipeline(video_path, args.config, description_override=description or None)

    with open(manifest_path) as f:
        manifest = json.load(f)

    platforms = [p.strip().lower() for p in args.platforms.split(",")]
    output_dir = os.path.dirname(os.path.abspath(manifest_path))
    urls_path = os.path.join(output_dir, "posted_urls.txt")

    print(f"\nPosting all {len(manifest)} clip(s) to {', '.join(platforms)} -- no review step ...")
    with open(urls_path, "a") as urls_file:
        for i, clip in enumerate(manifest, start=1):
            print(f"[{i}/{len(manifest)}] Posting {clip['clip']} ...")
            try:
                results = post_one(clip, platforms, public=not args.private)
                for platform, url in results:
                    urls_file.write(f"{clip['clip']}\t{platform}\t{url}\n")
                    urls_file.flush()
            except Exception as e:
                print(f"  Failed: {e}")

    print(f"\nDone. Posted URLs logged to {urls_path}")


if __name__ == "__main__":
    main()
