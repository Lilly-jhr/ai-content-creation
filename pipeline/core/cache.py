"""Content-addressed asset cache.

Every generated asset lives at outputs/<stage>/<item>/<key>.<ext> next to a sidecar
<key>.meta.json describing exactly how it was made. The filesystem is the index:
an asset is cached iff its file exists for the key computed from its inputs.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pipeline.core import config


def asset_dir(stage: str, item: str) -> Path:
    return config.OUTPUTS / stage / item


def asset_path(stage: str, item: str, key: str, ext: str) -> Path:
    return asset_dir(stage, item) / f"{key}.{ext.lstrip('.')}"


def meta_path(asset: Path) -> Path:
    return asset.with_suffix(".meta.json")


def lookup(stage: str, item: str, key: str, ext: str) -> Path | None:
    p = asset_path(stage, item, key, ext)
    return p if p.exists() and p.stat().st_size > 0 else None


def write_meta(asset: Path, meta: dict[str, Any]) -> None:
    meta_path(asset).write_text(json.dumps(meta, indent=2, ensure_ascii=False, default=str) + "\n")


def read_meta(asset: Path) -> dict[str, Any] | None:
    mp = meta_path(asset)
    return json.loads(mp.read_text()) if mp.exists() else None


def latest_meta(stage: str, item: str) -> dict[str, Any] | None:
    """Most recently written sidecar for an item: used by --dry-run to explain changes."""
    d = asset_dir(stage, item)
    if not d.exists():
        return None
    metas = sorted(d.glob("*.meta.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(metas[-1].read_text()) if metas else None


def changed_fields(old: dict[str, Any] | None, new: dict[str, Any]) -> list[str]:
    if old is None:
        return ["<new>"]
    old_inputs = old.get("inputs", {})
    keys = set(old_inputs) | set(new)
    return sorted(k for k in keys if old_inputs.get(k) != new.get(k))
