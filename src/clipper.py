"""Cut a clip out of the source video with ffmpeg (re-encoded for frame-accurate cuts)."""
from .ffmpeg_utils import run_ffmpeg


def cut_clip(source_path: str, start: float, end: float, out_path: str) -> None:
    duration = max(end - start, 0.1)
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{start:.3f}",
        "-i", source_path,
        "-t", f"{duration:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k",
        out_path,
    ]
    run_ffmpeg(cmd)
