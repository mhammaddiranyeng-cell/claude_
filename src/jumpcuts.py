"""Detect dead-air/silence within a clip and cut it out (jump cuts)."""
import re
import shutil
import subprocess
from typing import List, Tuple

from .ffmpeg_utils import run_ffmpeg


def detect_silences(video_path: str, noise_db: float = -30.0, min_duration: float = 0.35) -> List[Tuple[float, float]]:
    cmd = [
        "ffmpeg", "-i", video_path,
        "-af", f"silencedetect=noise={noise_db}dB:d={min_duration}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start:\s*([\d.]+)", result.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end:\s*([\d.]+)", result.stderr)]
    return list(zip(starts, ends))


def compute_keep_segments(
    duration: float,
    silences: List[Tuple[float, float]],
    padding: float = 0.12,
    min_keep: float = 0.4,
) -> List[Tuple[float, float]]:
    """Complement of the silence intervals, padded so speech isn't clipped."""
    trimmed = []
    for s, e in silences:
        s2, e2 = s + padding, e - padding
        if e2 > s2:
            trimmed.append((s2, e2))

    keep = []
    cursor = 0.0
    for s, e in trimmed:
        if s > cursor:
            keep.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < duration:
        keep.append((cursor, duration))

    keep = [(s, e) for s, e in keep if e - s >= min_keep]
    return keep or [(0.0, duration)]


def apply_jump_cuts(in_path: str, out_path: str, keep_segments: List[Tuple[float, float]]) -> None:
    if len(keep_segments) <= 1:
        shutil.copyfile(in_path, out_path)
        return

    filter_parts = []
    concat_inputs = []
    for i, (s, e) in enumerate(keep_segments):
        filter_parts.append(f"[0:v]trim=start={s:.3f}:end={e:.3f},setpts=PTS-STARTPTS[v{i}]")
        filter_parts.append(f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS[a{i}]")
        concat_inputs.append(f"[v{i}][a{i}]")
    n = len(keep_segments)
    filter_complex = ";".join(filter_parts) + f";{''.join(concat_inputs)}concat=n={n}:v=1:a=1[outv][outa]"

    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-filter_complex", filter_complex,
        "-map", "[outv]", "-map", "[outa]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        out_path,
    ]
    run_ffmpeg(cmd)


def remap_timestamp(t: float, keep_segments: List[Tuple[float, float]]) -> float:
    """Map a timestamp from the original (pre-jump-cut) clip to its new position."""
    cumulative = 0.0
    for s, e in keep_segments:
        if t < s:
            return cumulative
        if s <= t <= e:
            return cumulative + (t - s)
        cumulative += e - s
    return cumulative
