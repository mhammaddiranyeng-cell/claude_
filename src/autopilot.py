"""Fully unattended: drop one or more video paths + a description in at the
terminal prompt, and it edits AND posts every resulting clip with no review
step.

Usage:
    python -m src.autopilot --config config.yaml
    python -m src.autopilot --config config.yaml --platforms youtube,tiktok --private

At the prompt, drag/drop one file or several at once (most terminals paste
multiple dropped files as a single space-separated, individually-quoted
line -- that's parsed automatically), or type multiple paths yourself
separated by spaces.

Each video gets its own output_dir/<video-name>/ subfolder so clips from
different videos in the same batch don't overwrite each other. Videos are
processed one at a time: fully edited and posted before the next one starts.

Unlike src/pipeline.py + post/scheduler.py run separately (which stop after
editing so you can review clips first), this chains straight through to
posting. Use the two-step flow instead if you want to check clips before
they go out.
"""
import argparse
import json
import os
import re
import shlex

from dotenv import load_dotenv

from .pipeline import run as run_pipeline
from post.scheduler import post_one


def _slugify(name: str) -> str:
    """Filesystem- and ffmpeg-filter-safe folder name. ffmpeg's -vf
    subtitles= filter parses its path argument for syntax characters
    (', ,, :) rather than treating them as literal -- a stray apostrophe
    or comma in a source video's filename (e.g. "100 Children's Hearts.mp4")
    silently mangles the path instead of erroring clearly, so this strips
    anything but alphanumerics/space/hyphen up front."""
    safe = re.sub(r"[^A-Za-z0-9 _-]", "", name)
    return re.sub(r"\s+", "_", safe).strip("_") or "clip"


def _post_manifest(manifest_path: str, platforms: list, public: bool) -> None:
    with open(manifest_path) as f:
        manifest = json.load(f)

    output_dir = os.path.dirname(os.path.abspath(manifest_path))
    urls_path = os.path.join(output_dir, "posted_urls.txt")

    print(f"Posting all {len(manifest)} clip(s) to {', '.join(platforms)} -- no review step ...")
    with open(urls_path, "a") as urls_file:
        for i, clip in enumerate(manifest, start=1):
            print(f"[{i}/{len(manifest)}] Posting {clip['clip']} ...")
            try:
                results = post_one(clip, platforms, public=public)
                for platform, url in results:
                    urls_file.write(f"{clip['clip']}\t{platform}\t{url}\n")
                    urls_file.flush()
            except Exception as e:
                print(f"  Failed: {e}")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Unattended edit-and-post: drop video(s) in, they post themselves.")
    parser.add_argument("--config", default="config.yaml")
    parser.add_argument("--platforms", default="youtube,tiktok,instagram")
    parser.add_argument("--private", action="store_true", help="Upload YouTube as private instead of public.")
    args = parser.parse_args()

    raw = input("Drop video file path(s) here (one, or several dropped/typed at once): ").strip()
    candidates = shlex.split(raw)
    video_paths = [p for p in candidates if os.path.isfile(p)]
    skipped = [p for p in candidates if not os.path.isfile(p)]
    for p in skipped:
        print(f"  Skipping (not found): {p}")
    if not video_paths:
        raise SystemExit("No valid video file(s) given.")

    description = input(
        "Describe what's in these video(s) (used to pick editing style + hashtags for all of them; "
        "leave blank to use config.yaml's default): "
    ).strip()

    platforms = [p.strip().lower() for p in args.platforms.split(",")]

    for vi, video_path in enumerate(video_paths, start=1):
        print(f"\n=== [{vi}/{len(video_paths)}] {video_path} ===")
        subdir = _slugify(os.path.splitext(os.path.basename(video_path))[0])
        try:
            manifest_path = run_pipeline(video_path, args.config, description_override=description or None, output_subdir=subdir)
            _post_manifest(manifest_path, platforms, public=not args.private)
        except Exception as e:
            print(f"  Failed on this video, skipping to the next one: {e}")

    print(f"\nDone with all {len(video_paths)} video(s).")


if __name__ == "__main__":
    main()
