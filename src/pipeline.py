"""End-to-end: source video in -> reviewed, ready-to-post vertical clips out.

Usage:
    python -m src.pipeline --input source.mp4 --config config.yaml
"""
import argparse
import json
import math
import os

import yaml

from .transcribe import transcribe
from .highlights import find_highlights
from .clipper import cut_clip
from .jumpcuts import detect_silences, compute_keep_segments, apply_jump_cuts, remap_timestamp
from .reframe import reframe_vertical
from .zoom import apply_kenburns
from .captions import extract_words, build_srt, build_ass_karaoke, burn_subtitles
from .style import resolve_editing_config
from .probe import probe_duration_seconds


def run(input_path: str, config_path: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    output_dir = cfg.get("output_dir", "./output")
    os.makedirs(output_dir, exist_ok=True)

    print(f"[1/5] Transcribing {input_path} ...")
    segments = transcribe(input_path)

    print("[2/5] Scoring highlight candidates ...")
    clip_cfg = cfg["clipping"]

    max_clips_cfg = clip_cfg.get("max_clips_per_video", "auto")
    if max_clips_cfg == "auto":
        duration = probe_duration_seconds(input_path)
        max_clips = max(1, math.floor(duration / 60))
        print(f"  -> source is {duration / 60:.1f} min, auto-targeting {max_clips} clip(s)")
    else:
        max_clips = int(max_clips_cfg)

    highlights = find_highlights(
        segments,
        trigger_phrases=clip_cfg.get("trigger_phrases", []),
        min_clip_seconds=clip_cfg.get("min_clip_seconds", 20),
        max_clip_seconds=clip_cfg.get("max_clip_seconds", 90),
        max_clips=max_clips,
    )
    print(f"  -> {len(highlights)} candidate clips selected")

    reframe_cfg = cfg.get("reframe", {})
    captions_cfg = cfg.get("captions", {})
    campaign_cfg = cfg.get("campaign", {})
    editing_cfg = cfg.get("editing", {})

    style = resolve_editing_config(editing_cfg, campaign_cfg.get("description", ""))
    print(
        f"  -> editing style: jump_cuts={style.jump_cuts}, kenburns={style.kenburns}, "
        f"captions={style.caption_style}"
    )

    manifest = []
    reframe_width = reframe_cfg.get("width", 1080)
    reframe_height = reframe_cfg.get("height", 1920)

    for idx, h in enumerate(highlights, start=1):
        print(f"[3/5] Rendering clip {idx}/{len(highlights)} ({h.start:.1f}s-{h.end:.1f}s) ...")
        base = os.path.join(output_dir, f"clip_{idx:02d}")
        raw_path = f"{base}_raw.mp4"
        jumpcut_path = f"{base}_jumpcut.mp4"
        vertical_path = f"{base}_vertical.mp4"
        zoomed_path = f"{base}_zoomed.mp4"
        subtitle_path = f"{base}.ass" if style.caption_style == "karaoke" else f"{base}.srt"
        final_path = f"{base}_final.mp4"

        clip_duration = h.end - h.start
        cut_clip(input_path, h.start, h.end, raw_path)

        if style.jump_cuts:
            print(f"    [jump cuts] detecting dead air ...")
            silences = detect_silences(raw_path, min_duration=style.silence_min_duration)
            keep_segments = compute_keep_segments(clip_duration, silences)
            apply_jump_cuts(raw_path, jumpcut_path, keep_segments)
            removed = clip_duration - sum(e - s for s, e in keep_segments)
            print(f"    [jump cuts] removed {removed:.1f}s of dead air across {len(keep_segments)} segments")
        else:
            jumpcut_path = raw_path
            keep_segments = [(0.0, clip_duration)]

        reframe_vertical(jumpcut_path, vertical_path, mode=reframe_cfg.get("mode", "blur-bg"), width=reframe_width, height=reframe_height)

        if style.kenburns:
            apply_kenburns(vertical_path, zoomed_path, width=reframe_width, height=reframe_height)
        else:
            zoomed_path = vertical_path

        if captions_cfg.get("enabled", True):
            words = extract_words(segments, h.start, h.end)
            words = [
                (remap_timestamp(s, keep_segments), remap_timestamp(e, keep_segments), t)
                for s, e, t in words
            ]
            words = [(s, e, t) for s, e, t in words if e > s]

            font = captions_cfg.get("font", "Arial")
            font_size = captions_cfg.get("font_size", 46)
            max_words = captions_cfg.get("max_words_per_line", 4)
            position = captions_cfg.get("position", "bottom")

            if style.caption_style == "karaoke":
                build_ass_karaoke(words, subtitle_path, font=font, font_size=font_size, max_words_per_line=max_words, position=position)
                burn_subtitles(zoomed_path, subtitle_path, final_path)
            else:
                build_srt(words, subtitle_path, max_words_per_line=max_words)
                alignment = 2 if position == "bottom" else 5
                force_style = f"FontName={font},FontSize={font_size},Alignment={alignment},Outline=3,Bold=1,MarginV=80,MarginL=60,MarginR=60"
                burn_subtitles(zoomed_path, subtitle_path, final_path, force_style=force_style)
        else:
            os.replace(zoomed_path, final_path)

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
            "editing_style": {
                "jump_cuts": style.jump_cuts,
                "kenburns": style.kenburns,
                "caption_style": style.caption_style,
            },
        })

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"[5/5] Done. {len(manifest)} clips ready for review in {output_dir}")
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
