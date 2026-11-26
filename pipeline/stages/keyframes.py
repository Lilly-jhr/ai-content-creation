"""Stage: keyframes. One still per shot, conditioned on the approved reference images.

The character and location description blocks and the style block are attached verbatim
to every prompt, because drift mostly comes from re-describing things differently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PIL import Image

from pipeline.core import cache, config
from pipeline.core.calls import CTX, call_model, compute_key
from pipeline.core.config import provider_cfg
from pipeline.core.hashing import hash_file
from pipeline.models import Shot, Storyboard
from pipeline.providers.cloudflare import CloudflareImage
from pipeline.stages import refs as refs_stage

STAGE = "keyframes"


class RefsNotApproved(RuntimeError):
    pass


def ref_paths(sb: Storyboard, shot: Shot) -> list[Path]:
    if not shot.keyframe.use_refs:
        return []
    ids = list(shot.characters) + ([shot.location] if shot.location else [])
    paths = []
    for rid in ids:
        has_ref = any(sid == rid for sid, _, _ in refs_stage.subjects(sb))
        if not has_ref:
            continue
        p = refs_stage.approved_path(sb, rid)
        if p is None:
            raise RefsNotApproved(
                f"{shot.id}: reference '{rid}' is not approved/generated. Run `refs`, choose a seed, "
                f"then `approve refs {rid}` (or pass --allow-draft for a rough cut)."
            )
        is_character = any(c.id == rid for c in sb.characters)
        paths.append(portrait_crop(p) if is_character else p)
    return paths[:4]


def portrait_crop(ref: Path) -> Path:
    """Character sheets are two panels (full body | head-and-shoulders). Feeding the whole
    sheet made klein copy the two-panel layout into scenes (duplicated people, EXPERIMENTS E3b),
    so characters are conditioned on the portrait panel only. Deterministic derived file."""
    out = ref.with_name(f"{ref.stem}.portrait.png")
    if not out.exists():
        img = Image.open(ref).convert("RGB")
        w, h = img.size
        img.crop((w // 2, 0, w, h)).save(out)
    return out


def build_prompt(sb: Storyboard, shot: Shot) -> str:
    blocks = []
    if shot.characters:  # only shots with people risk copying the two-panel sheet layout (E3b)
        blocks.append(
            "A single cinematic film frame of one moment, not a reference sheet, not a split panel."
        )
    blocks.append(shot.keyframe.prompt)
    blocks += [sb.character(c).description for c in shot.characters]
    if shot.location:
        blocks.append(sb.location(shot.location).description)
    blocks.append(f"Lighting: {shot.lighting}. Composition: {shot.composition}.")
    blocks.append(sb.meta.style_block)
    return " ".join(b.strip() for b in blocks if b)


def inputs_for(
    sb: Storyboard, shot: Shot, seed: int | None = None
) -> tuple[dict[str, Any], list[Path]]:
    refs = ref_paths(sb, shot)
    kf = shot.keyframe
    if kf.composition_ref:
        comp = config.ROOT / kf.composition_ref
        if not comp.exists():
            raise FileNotFoundError(f"{shot.id}: composition_ref {kf.composition_ref} not found")
        refs = [comp, *refs][:4]
    if kf.extra_refs:
        extra = [config.ROOT / r for r in kf.extra_refs]
        missing = [str(r) for r in extra if not r.exists()]
        if missing:
            raise FileNotFoundError(f"{shot.id}: extra_refs not found: {missing}")
        refs = [*extra, *refs][:4]
    return (
        {
            "prompt": build_prompt(sb, shot),
            "seed": kf.seed if seed is None else seed,
            "width": kf.width,
            "height": kf.height,
            "ref_hashes": [hash_file(p) for p in refs],
        },
        refs,
    )


def current_path(sb: Storyboard, shot: Shot, require_approved: bool = True) -> Path | None:
    """The keyframe the downstream stages should use (approved, or any cached with --allow-draft)."""
    try:
        inputs, _ = inputs_for(sb, shot)
    except RefsNotApproved:
        return None
    prov = CloudflareImage()
    key = compute_key(STAGE, prov.name, prov.model, inputs)
    if require_approved and shot.keyframe.approved_key != key and not CTX.allow_draft:
        return None
    return cache.lookup(STAGE, shot.id, key, "png")


def run(sb: Storyboard, candidates: int = 1) -> None:
    prov = CloudflareImage()
    for shot in sb.shots:
        if not CTX.wants(shot.id):
            continue
        for i in range(candidates):
            inputs, refs = inputs_for(sb, shot, seed=shot.keyframe.seed + i)
            call_model(
                stage=STAGE,
                item=shot.id,
                provider=prov.name,
                model=prov.model,
                inputs=inputs,
                ext="png",
                licence=provider_cfg("image")["licence"],
                run=lambda tmp, inputs=inputs, refs=refs: prov.generate(
                    inputs["prompt"],
                    tmp,
                    seed=inputs["seed"],
                    width=inputs["width"],
                    height=inputs["height"],
                    refs=refs,
                ),
            )
