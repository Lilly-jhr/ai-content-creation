"""Stage: subtitles. English captions timed to the measured narration, one ASS file per ratio.

Rules (film-delivery): at most 2 lines of at most 40 characters, kept inside the safe area
(vertical video keeps clear of the platform UI at the bottom and right).
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Any

from pipeline.core import config
from pipeline.models import Storyboard

STAGE = "subs"
MAX_CHARS = 40
MAX_LINES = 2

LAYOUTS: dict[str, dict[str, int]] = {
    # PlayRes matches the export size, so margins are in output pixels.
    "16x9": {"w": 1920, "h": 1080, "size": 50, "margin_v": 80, "margin_lr": 240},
    "9x16": {"w": 1080, "h": 1920, "size": 54, "margin_v": 460, "margin_lr": 110},
}
FONT = "Noto Sans"


def chunk(text: str) -> list[list[str]]:
    """Split text into subtitle events of <= MAX_LINES lines of <= MAX_CHARS characters."""
    lines = textwrap.wrap(" ".join(text.split()), MAX_CHARS, break_long_words=False)
    return [lines[i : i + MAX_LINES] for i in range(0, len(lines), MAX_LINES)]


def events(sb: Storyboard, timeline: dict[str, Any]) -> list[tuple[float, float, str]]:
    out: list[tuple[float, float, str]] = []
    by_id = {s["id"]: s for s in timeline["shots"]}
    for shot in sb.shots:
        t = by_id[shot.id]
        if not shot.narration or not t["vo_start"]:
            continue
        parts = chunk(shot.narration.text_en)
        weights = [sum(len(line) for line in p) for p in parts]
        total_w = sum(weights) or 1
        start = t["vo_start"]
        span = t["vo_duration"] + 0.3  # let the last caption linger slightly
        for part, w in zip(parts, weights, strict=True):
            dur = span * w / total_w
            out.append((start, start + dur, r"\N".join(part)))
            start += dur
    return out


def _ts(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def ass(ratio: str, evs: list[tuple[float, float, str]]) -> str:
    lay = LAYOUTS[ratio]
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {lay["w"]}
PlayResY: {lay["h"]}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT},{lay["size"]},&H00FFFFFF,&H000000FF,&H00101010,&H64000000,0,0,0,0,100,100,0,0,1,2.6,1.2,2,{lay["margin_lr"]},{lay["margin_lr"]},{lay["margin_v"]},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    body = "".join(f"Dialogue: 0,{_ts(a)},{_ts(b)},Default,,0,0,0,,{text}\n" for a, b, text in evs)
    return header + body


def srt(evs: list[tuple[float, float, str]]) -> str:
    def ts(x: float) -> str:
        ms = int(round(x * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    return "".join(
        f"{i}\n{ts(a)} --> {ts(b)}\n{t.replace(chr(92) + 'N', chr(10))}\n\n"
        for i, (a, b, t) in enumerate(evs, 1)
    )


def run(sb: Storyboard, timeline: dict[str, Any]) -> dict[str, Path]:
    evs = events(sb, timeline)
    out_dir = config.OUTPUTS / STAGE
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = {}
    for ratio in LAYOUTS:
        p = out_dir / f"{ratio}.ass"
        p.write_text(ass(ratio, evs), encoding="utf-8")
        paths[ratio] = p
    (out_dir / "en.srt").write_text(srt(evs), encoding="utf-8")
    print(f"[subtitles] {len(evs)} events -> {out_dir.relative_to(config.ROOT)}")
    return paths
