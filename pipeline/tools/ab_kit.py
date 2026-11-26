"""E9 blind A/B kit: for chosen shots, render the Wan clip and the Ken Burns version of the same shot,
same length and crop, with randomised labels X/Y. The key is written next to them (gitignored)."""

from __future__ import annotations

import json
import random

from pipeline.core import config
from pipeline.models import Storyboard
from pipeline.stages import assemble, keyframes, video

SHOTS = ("s02", "s03", "s07")


def run(sb: Storyboard, timeline: dict, ratio: str = "9x16", seed: int = 7) -> dict:
    rng = random.Random(seed)
    out_dir = config.OUTPUTS / "review" / "e9_ab"
    out_dir.mkdir(parents=True, exist_ok=True)
    tl = {s["id"]: s for s in timeline["shots"]}
    key = {}
    common = ["-r", "24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-an"]
    for sid in SHOTS:
        shot = sb.shot(sid)
        length = tl[sid]["duration"]
        clip = video.cached_clip(sb, shot, "16x9")
        kf = keyframes.current_path(sb, shot)
        if not clip or not kf:
            continue
        labels = ["X", "Y"]
        rng.shuffle(labels)
        wan_out = out_dir / f"{sid}_{labels[0]}.mp4"
        kb_out = out_dir / f"{sid}_{labels[1]}.mp4"
        assemble.render_wan_segment(shot, ratio, clip, length, wan_out, common)
        frames = max(int(round(length * 24)), 2)
        assemble.media.run(
            [
                "-i",
                str(kf),
                "-vf",
                assemble._kenburns_filter(shot, ratio, frames),
                "-frames:v",
                str(frames),
                *common,
                str(kb_out),
            ]
        )
        key[sid] = {labels[0]: "wan", labels[1]: "kenburns"}
    (out_dir / "KEY_do_not_share.json").write_text(json.dumps(key, indent=2) + "\n")
    return key
