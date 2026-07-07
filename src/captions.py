"""Build an SRT for a clip window and burn it into the video."""
import subprocess
from typing import List

from .transcribe import Segment


def _fmt_ts(seconds: float) -> str:
    ms = int(round(seconds * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(segments: List[Segment], clip_start: float, clip_end: float, srt_path: str, max_words_per_line: int = 6) -> None:
    words = [w for s in segments for w in s.words if clip_start <= w.start < clip_end]

    entries = []
    for i in range(0, len(words), max_words_per_line):
        chunk = words[i:i + max_words_per_line]
        if not chunk:
            continue
        entries.append((chunk[0].start - clip_start, chunk[-1].end - clip_start, " ".join(w.text for w in chunk)))

    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(entries, start=1):
            f.write(f"{idx}\n{_fmt_ts(max(start, 0))} --> {_fmt_ts(max(end, 0))}\n{text}\n\n")


def burn_captions(in_path: str, srt_path: str, out_path: str, font: str = "Arial", font_size: int = 64, position: str = "bottom") -> None:
    alignment = 2 if position == "bottom" else 5  # libass numpad alignment codes
    style = f"FontName={font},FontSize={font_size},Alignment={alignment},Outline=3,Bold=1"
    vf = f"subtitles={srt_path}:force_style='{style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        out_path,
    ]
    subprocess.run(cmd, check=True, capture_output=True)
