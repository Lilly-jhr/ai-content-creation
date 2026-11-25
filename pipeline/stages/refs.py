"""Stage: reference sheets. Characters and locations are locked BEFORE any keyframe.

`--candidates N` explores seeds seed..seed+N-1 (each its own cached asset). You pick one by
setting `ref.seed` in storyboard.json and running `python -m pipeline approve refs <id>`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.core import cache
from pipeline.core.calls import CTX, call_model, compute_key
from pipeline.core.config import provider_cfg
from pipeline.models import RefImage, Storyboard
from pipeline.providers.cloudflare import CloudflareImage

STAGE = "refs"


def subjects(sb: Storyboard) -> list[tuple[str, str, RefImage]]:
    """(id, description block, ref spec) for every character and location with a ref."""
    items = [(c.id, c.description, c.ref) for c in sb.characters]
    items += [(loc.id, loc.description, loc.ref) for loc in sb.locations if loc.ref]
    return items


def inputs_for(
    sb: Storyboard, description: str, ref: RefImage, seed: int | None = None
) -> dict[str, Any]:
    prompt = f"{ref.prompt} {description} {sb.meta.style_block}".strip()
    return {
        "prompt": prompt,
        "seed": ref.seed if seed is None else seed,
        "width": ref.width,
        "height": ref.height,
    }


def key_for(inputs: dict[str, Any]) -> str:
    prov = CloudflareImage()
    return compute_key(STAGE, prov.name, prov.model, inputs)


def approved_path(sb: Storyboard, item_id: str) -> Path | None:
    """Path of the approved ref for a character/location, or (with --allow-draft) its current one."""
    for sid, desc, ref in subjects(sb):
        if sid != item_id:
            continue
        key = key_for(inputs_for(sb, desc, ref))
        if ref.approved_key == key or CTX.allow_draft:
            return cache.lookup(STAGE, sid, key, "png")
        return None
    return None


def run(sb: Storyboard, candidates: int = 1, only: set[str] | None = None) -> None:
    prov = CloudflareImage()
    for sid, desc, ref in subjects(sb):
        if only and sid not in only:
            continue
        for i in range(candidates):
            inputs = inputs_for(sb, desc, ref, seed=ref.seed + i)
            call_model(
                stage=STAGE,
                item=sid,
                provider=prov.name,
                model=prov.model,
                inputs=inputs,
                ext="png",
                licence=provider_cfg("image")["licence"],
                run=lambda tmp, inputs=inputs: prov.generate(
                    inputs["prompt"],
                    tmp,
                    seed=inputs["seed"],
                    width=inputs["width"],
                    height=inputs["height"],
                    refs=[],
                ),
            )
