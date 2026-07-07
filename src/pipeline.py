"""End-to-end: source video in -> reviewed, ready-to-post vertical clips out.

Usage:
    python -m src.pipeline --input source.mp4 --config config.yaml
"""
import argparse
import json
import os

import yaml

from .transcribe import transcribe
from .highlights import find_highlights
from .clipper import cut_clip
from .reframe import reframe_vertical
from .captions import build_srt, burn_captions


def run(input_path: str, config_path: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    output_dir = cfg.get("output_dir", "./output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"[1/4] Transcribing {input_path} ...")
    segments = transcribe(input_path)

    print("[2/4] Scoring highlight candidates ...")
    clip_cfg = cfg["clipping"]
    highlights = find_highlights(
        segments,
        trigger_phrases=clip_cfg.get("trigger_phrases", []),
        min_clip_seconds=clip_cfg.get("min_clip_seconds", 20),
        max_clip_seconds=clip_cfg.get("max_clip_seconds", 90),
        max_clips=clip_cfg.get("max_clips_per_video", 8),
    )
    print(f"  -> {len(highlights)} candidate clips selected")

    manifest = []
    reframe_cfg = cfg.get("reframe", {})
    captions_cfg = cfg.get("captions", {})
    campaign_cfg = cfg.get("campaign", {})

    for idx, h in enumerate(highlights, start=1):
        print(f"[3/4] Rendering clip {idx}/{len(highlights)} ({h.start:.1f}s-{h.end:.1f}s) ...")
        base = os.path.join(output_dir, f"clip_{idx:02d}")
        raw_path = f"{base}_raw.mp4"
        vertical_path = f"{base}_vertical.mp4"
        srt_path = f"{base}.srt"
        final_path = f"{base}_final.mp4"

        cut_clip(input_path, h.start, h.end, raw_path)
        reframe_vertical(
            raw_path, vertical_path,
            mode=reframe_cfg.get("mode", "blur-bg"),
            width=reframe_cfg.get("width", 1080),
            height=reframe_cfg.get("height", 1920),
        )

        if captions_cfg.get("enabled", True):
            build_srt(segments, h.start, h.end, srt_path)
            burn_captions(
                vertical_path, srt_path, final_path,
                font=captions_cfg.get("font", "Arial"),
                font_size=captions_cfg.get("font_size", 64),
                position=captions_cfg.get("position", "bottom"),
            )
        else:
            os.replace(vertical_path, final_path)

        hashtags = " ".join(campaign_cfg.get("hashtags", []))
        title = h.text[:80].strip()
        caption = campaign_cfg.get("caption_template", "{title} {hashtags}").format(title=title, hashtags=hashtags)

        manifest.append({
            "clip": final_path,
            "start": h.start,
            "end": h.end,
            "score": h.score,
            "transcript": h.text,
            "suggested_caption": caption,
        })

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[4/4] Done. {len(manifest)} clips ready for review in {output_dir}")
    print(f"       Manifest: {manifest_path}")
    print("       Review each clip before posting -- nothing is auto-posted by this pipeline.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-clip a source video into vertical shorts.")
    parser.add_argument("--input", required=True, help="Path to source video (mp4/mov/etc).")
    parser.add_argument("--config", default="config.yaml", help="Path to campaign config yaml.")
    args = parser.parse_args()
    run(args.input, args.config)


if __name__ == "__main__":
    main()
