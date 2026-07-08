"""Shared ffmpeg subprocess runner that surfaces stderr on failure."""
import subprocess


def run_ffmpeg(cmd: list) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"ffmpeg failed (exit {result.returncode}):\n"
            f"command: {' '.join(cmd)}\n\n"
            f"stderr:\n{result.stderr}"
        )
