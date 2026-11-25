"""Small FFmpeg/ffprobe helpers (deterministic, no AI)."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path


class MediaError(RuntimeError):
    pass


def require_ffmpeg() -> None:
    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            raise MediaError(f"{tool} not found on PATH; install FFmpeg >= 6")


def run(args: list[str], *, quiet: bool = True) -> subprocess.CompletedProcess[str]:
    cmd = ["ffmpeg", "-hide_banner", "-y", *(["-loglevel", "error"] if quiet else []), *args]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise MediaError(f"ffmpeg failed ({proc.returncode}): {proc.stderr[-1500:]}")
    return proc


def probe(path: Path) -> dict:
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise MediaError(f"ffprobe failed on {path}: {proc.stderr}")
    return json.loads(proc.stdout)


def duration(path: Path) -> float:
    return float(probe(path)["format"]["duration"])


def to_wav(src: Path, dst: Path, *, sample_rate: int = 48000, channels: int = 1) -> None:
    """Normalise any audio file to PCM WAV, trimming leading/trailing digital silence."""
    trim = (
        "silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.05,"
        "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.1,areverse"
    )
    run(
        [
            "-i",
            str(src),
            "-af",
            trim,
            "-ar",
            str(sample_rate),
            "-ac",
            str(channels),
            "-c:a",
            "pcm_s16le",
            "-f",
            "wav",
            str(dst),
        ]
    )
