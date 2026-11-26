"""Build the showcase site's data + web-sized media from the pipeline's own records.

`python -m pipeline site` -> site/data/*.json and site/media/*. Everything on the page is derived from
storyboard.json, outputs/timeline.json, runs.jsonl and the cached assets, so the site can't drift from the film.
"""

from __future__ import annotations

import json
from collections import defaultdict
from statistics import median

from PIL import Image

from pipeline.core import config, media, runlog
from pipeline.models import Storyboard
from pipeline.stages import keyframes, refs, video

SITE = config.ROOT / "site"
CHAPTERS = {
    1: "Great-grandparents",
    2: "Grandmother",
    3: "My mother",
    4: "Raising me",
    5: "Me",
}


def _jpg(src, dst, width: int) -> None:
    img = Image.open(src).convert("RGB")
    img.thumbnail((width, width * 2), Image.LANCZOS)
    img.save(dst, "JPEG", quality=82, optimize=True, progressive=True)


def build(sb: Storyboard, films: bool = True) -> dict:
    data_dir, med = SITE / "data", SITE / "media"
    for d in (data_dir, med / "shots", med / "clips", med / "people"):
        d.mkdir(parents=True, exist_ok=True)
    tl = json.loads((config.OUTPUTS / "timeline.json").read_text())
    t_by = {s["id"]: s for s in tl["shots"]}
    final = json.loads((config.OUTPUTS / "final" / "a_little_further_9x16.json").read_text())

    shots = []
    for s in sb.shots:
        kf = keyframes.current_path(sb, s)
        if kf:
            _jpg(kf, med / "shots" / f"{s.id}.jpg", 960)
        clip = video.cached_clip(sb, s, "16x9")
        if clip:
            media.run(
                [
                    "-i",
                    str(clip),
                    "-vf",
                    "scale=640:-2",
                    "-an",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "30",
                    "-preset",
                    "slow",
                    "-movflags",
                    "+faststart",
                    str(med / "clips" / f"{s.id}.mp4"),
                ]
            )
        t = t_by[s.id]
        shots.append(
            {
                "id": s.id,
                "seq": s.seq,
                "chapter": s.chapter,
                "chapter_name": CHAPTERS[s.chapter],
                "start": t["start"],
                "duration": t["duration"],
                "purpose": s.purpose,
                "beat": s.emotional_beat,
                "size": s.shot_size,
                "camera": s.camera_move,
                "light": s.lighting,
                "narration_am": s.narration.text if s.narration else "",
                "narration_en": s.narration.text_en if s.narration else "",
                "keyframe_prompt": s.keyframe.prompt,
                "seed": s.keyframe.seed,
                "keyframe_key": s.keyframe.approved_key,
                "source_shot": s.keyframe.source_shot,
                "motion_prompt": s.motion.prompt,
                "segment": final["segments"].get(s.id),
                "vertical_center": s.keyframe.vertical_center,
                "image": f"media/shots/{(s.keyframe.source_shot or s.id)}.jpg" if kf else None,
                "clip": f"media/clips/{s.id}.mp4" if clip else None,
                "fact_flags": [f.model_dump() for f in s.fact_flags],
            }
        )

    people = []
    for c in sb.characters:
        p = refs.approved_path(sb, c.id)
        if p:
            img = Image.open(p).convert("RGB")
            w, h = img.size
            img.crop((w // 2, 0, w, h)).resize((360, 360 * h // (w // 2))).save(
                med / "people" / f"{c.id}.jpg", "JPEG", quality=82, optimize=True
            )
        people.append(
            {
                "id": c.id,
                "role": c.role,
                "chapter": c.chapter,
                "image": f"media/people/{c.id}.jpg" if p else None,
            }
        )

    rows = runlog.read()
    by_stage: dict[str, dict] = defaultdict(
        lambda: {"calls": 0, "ok": 0, "error": 0, "lat": [], "gpu_s": 0.0, "models": set()}
    )
    for r in rows:
        st = by_stage[r.get("stage", "?")]
        st["calls"] += 1
        st["ok" if r.get("status") == "ok" else "error"] += 1
        if r.get("status") == "ok" and r.get("latency_s") is not None:
            st["lat"].append(float(r["latency_s"]))
        st["gpu_s"] += float(r.get("gpu_s") or 0)
        st["models"].add(r.get("model", "?"))
    stages = [
        {
            "stage": k,
            "calls": v["calls"],
            "ok": v["ok"],
            "error": v["error"],
            "median_latency_s": round(median(v["lat"]), 1) if v["lat"] else None,
            "gpu_min": round(v["gpu_s"] / 60, 1),
            "models": sorted(v["models"]),
        }
        for k, v in by_stage.items()
    ]
    stages.sort(key=lambda x: -x["calls"])

    meta = {
        "title": sb.meta.title,
        "logline": sb.meta.logline,
        "intent": sb.meta.intent,
        "total_s": tl["total"],
        "end_card": sb.end_card.lines,
        "language": sb.meta.language,
        "calls": len(rows),
        "ok": sum(r.get("status") == "ok" for r in rows),
        "gpu_min": round(sum(float(r.get("gpu_s") or 0) for r in rows) / 60, 1),
        "segments": final["summary"],
        "music_seed": sb.music.chosen_seed,
        "music_why": sb.music.why,
    }
    (data_dir / "shots.json").write_text(json.dumps(shots, ensure_ascii=False, indent=1))
    (data_dir / "people.json").write_text(json.dumps(people, ensure_ascii=False, indent=1))
    (data_dir / "stages.json").write_text(json.dumps(stages, ensure_ascii=False, indent=1))
    (data_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1))
    # standalone index.html for static hosting (Vercel / GitHub Pages); page.html is the body
    head = (
        '<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
        "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n</head>\n<body>\n"
    )
    (SITE / "index.html").write_text(
        head + (SITE / "page.html").read_text() + "\n</body>\n</html>\n"
    )

    if films:
        fin = config.OUTPUTS / "final"
        for ratio, scale in (("9x16", "540:960"), ("16x9", "960:540")):
            media.run(
                [
                    "-i",
                    str(fin / f"a_little_further_{ratio}.mp4"),
                    "-vf",
                    f"scale={scale}",
                    "-c:v",
                    "libx264",
                    "-crf",
                    "27",
                    "-preset",
                    "slow",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "128k",
                    "-movflags",
                    "+faststart",
                    str(med / f"film_{ratio}.mp4"),
                ]
            )
        media.run(
            [
                "-i",
                str(fin / "radio_cut.mp4"),
                "-vn",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "128k",
                str(med / "radio_cut.mp3"),
            ]
        )
        _jpg(med / "shots" / "s01.jpg", med / "poster_16x9.jpg", 960)
        media.run(
            [
                "-ss",
                "40",
                "-i",
                str(med / "film_9x16.mp4"),
                "-frames:v",
                "1",
                "-update",
                "1",
                str(med / "poster_9x16.jpg"),
            ]
        )
    return meta
