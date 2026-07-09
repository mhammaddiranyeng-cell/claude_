"""Subtle Ken Burns zoom for an otherwise-static shot (e.g. talking head)."""
from .ffmpeg_utils import run_ffmpeg


def apply_kenburns(
    in_path: str, out_path: str,
    width: int = 1080, height: int = 1920, fps: int = 30,
    max_zoom: float = 1.15, rate: float = 0.0006,
) -> None:
    # Upscale first so zoompan has enough source resolution to crop from
    # without visible pixelation; pzoom carries the zoom level frame-to-frame
    # (plain "zoom" resets every frame when the input is video, not a still).
    # The fps= filter *before* zoompan is required: zoompan was designed for
    # single-image input and stretches the timeline (rather than resampling)
    # when the input isn't already at the exact fps it's told to output --
    # e.g. a 12fps source with fps=30 requested here doubles the output
    # duration instead of just changing frame count, desyncing audio/video.
    vf = (
        f"scale={width * 4}:-2,"
        f"fps={fps},"
        f"zoompan=z='min(pzoom+{rate},{max_zoom})':d=1:"
        f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={width}x{height}:fps={fps}"
    )
    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-vf", vf,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "copy",
        out_path,
    ]
    run_ffmpeg(cmd)
