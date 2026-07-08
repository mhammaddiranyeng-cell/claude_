"""Build captions (plain line-by-line or karaoke word-by-word) and burn them in.

All functions here work in the OUTPUT clip's local time (0 = start of the
final clip), not the source video's absolute time -- callers are
responsible for converting/remapping (see pipeline.py, which remaps
through any jump cuts before calling these).
"""
from typing import List, Tuple

from .ffmpeg_utils import run_ffmpeg
from .transcribe import Segment

WordEntry = Tuple[float, float, str]  # (local_start, local_end, text)


def extract_words(segments: List[Segment], clip_start: float, clip_end: float) -> List[WordEntry]:
    """Pull words in [clip_start, clip_end) and convert to clip-local time."""
    return [
        (w.start - clip_start, w.end - clip_start, w.text)
        for s in segments for w in s.words
        if clip_start <= w.start < clip_end
    ]


def _fmt_srt_ts(seconds: float) -> str:
    ms = int(round(max(seconds, 0) * 1000))
    h, ms = divmod(ms, 3_600_000)
    m, ms = divmod(ms, 60_000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def build_srt(words: List[WordEntry], srt_path: str, max_words_per_line: int = 4) -> None:
    entries = []
    for i in range(0, len(words), max_words_per_line):
        chunk = words[i:i + max_words_per_line]
        if not chunk:
            continue
        entries.append((chunk[0][0], chunk[-1][1], " ".join(w[2] for w in chunk)))

    with open(srt_path, "w", encoding="utf-8") as f:
        for idx, (start, end, text) in enumerate(entries, start=1):
            f.write(f"{idx}\n{_fmt_srt_ts(start)} --> {_fmt_srt_ts(end)}\n{text}\n\n")


def _fmt_ass_ts(seconds: float) -> str:
    cs = int(round(max(seconds, 0) * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h:01d}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass_karaoke(
    words: List[WordEntry], ass_path: str,
    font: str = "Arial", font_size: int = 46, max_words_per_line: int = 4,
    highlight_color: str = "&H0000FFFF",  # ASS is BGR: this is yellow
    position: str = "bottom",
) -> None:
    alignment = 2 if position == "bottom" else 5
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{font},{font_size},{highlight_color},&H00FFFFFF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,{alignment},60,60,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = []
    for i in range(0, len(words), max_words_per_line):
        chunk = words[i:i + max_words_per_line]
        if not chunk:
            continue
        line_start, line_end = chunk[0][0], chunk[-1][1]
        karaoke_text = "".join(
            f"{{\\k{max(int(round((we - ws) * 100)), 1)}}}{wtext} " for ws, we, wtext in chunk
        )
        lines.append(
            f"Dialogue: 0,{_fmt_ass_ts(line_start)},{_fmt_ass_ts(line_end)},Default,,0,0,0,,{karaoke_text.strip()}"
        )

    with open(ass_path, "w", encoding="utf-8") as f:
        f.write(header)
        f.write("\n".join(lines) + "\n")


def burn_subtitles(in_path: str, subtitle_path: str, out_path: str, force_style: str = None) -> None:
    vf = f"subtitles={subtitle_path}"
    if force_style:
        vf += f":force_style='{force_style}'"

    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        out_path,
    ]
    run_ffmpeg(cmd)
