"""Contact sheets for approval: every cached candidate of a stage, labelled with item + seed."""

from __future__ import annotations

import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from pipeline.core import config

THUMB = 300  # thumbnail height; width follows the image aspect ratio


def sheet(stage: str, items: list[str] | None = None, latest: int | None = None) -> Path:
    root = config.OUTPUTS / stage
    rows: list[tuple[str, list[tuple[Path, dict]]]] = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        if items and d.name not in items:
            continue
        cands = []
        for meta_p in sorted(d.glob("*.meta.json"), key=lambda p: p.stat().st_mtime):
            meta = json.loads(meta_p.read_text())
            img = meta_p.with_name(meta_p.name.replace(".meta.json", ".png"))
            if img.exists():
                cands.append((img, meta))
        if latest:
            cands = cands[-latest:]
        if cands:
            rows.append((d.name, cands))
    cols = max(len(c) for _, c in rows)
    aspect = max(Image.open(c[0]).width / Image.open(c[0]).height for _, cs in rows for c in cs)
    tw = int(THUMB * aspect)
    label_w = 230
    font = ImageFont.truetype(str(config.FONTS / "NotoSans[wdth,wght].ttf"), 20)
    out = Image.new("RGB", (label_w + cols * (tw + 10), len(rows) * (THUMB + 40)), (24, 22, 20))
    draw = ImageDraw.Draw(out)
    for r, (name, cands) in enumerate(rows):
        y = r * (THUMB + 40)
        draw.text((10, y + THUMB // 2), name, font=font, fill=(235, 225, 210))
        for c, (img, meta) in enumerate(cands):
            x = label_w + c * (tw + 10)
            im = Image.open(img).convert("RGB")
            out.paste(im.resize((int(THUMB * im.width / im.height), THUMB)), (x, y))
            draw.text(
                (x + 4, y + THUMB + 6),
                f"seed {meta['inputs']['seed']}  {meta['key'][:6]}",
                font=font,
                fill=(200, 190, 175),
            )
    dst = config.OUTPUTS / "review" / f"{stage}_sheet.png"
    dst.parent.mkdir(parents=True, exist_ok=True)
    out.save(dst)
    return dst
