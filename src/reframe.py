"""Reframe a horizontal (or mixed) clip into a vertical 9:16 output."""
from .ffmpeg_utils import run_ffmpeg


def reframe_vertical(in_path: str, out_path: str, mode: str = "blur-bg", width: int = 1080, height: int = 1920) -> None:
    if mode == "center-crop":
        vf = f"crop=ih*{width}/{height}:ih,scale={width}:{height},setsar=1"
    else:  # blur-bg: blurred, scaled copy fills the frame; sharp copy centered on top
        vf = (
            f"split=2[bg][fg];"
            f"[bg]scale={width}:{height},crop={width}:{height},gblur=sigma=20,setsar=1[bg];"
            f"[fg]scale={width}:-2,setsar=1[fg];"
            f"[bg][fg]overlay=(W-w)/2:(H-h)/2"
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
