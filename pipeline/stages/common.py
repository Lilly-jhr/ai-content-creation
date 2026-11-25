"""Helpers shared by stages: load + validate the storyboard, read/write approvals."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from pipeline.core import config
from pipeline.models import Storyboard


class StoryboardError(RuntimeError):
    pass


def load_raw(path: Path | None = None) -> dict[str, Any]:
    return json.loads((path or config.STORYBOARD).read_text(encoding="utf-8"))


def load(path: Path | None = None) -> Storyboard:
    """Every stage starts here: the storyboard is validated before any work happens."""
    try:
        return Storyboard.model_validate(load_raw(path))
    except ValidationError as exc:
        lines = [
            f"  - {'.'.join(map(str, e['loc'])) or '<root>'}: {e['msg']}" for e in exc.errors()
        ]
        raise StoryboardError("storyboard.json is invalid:\n" + "\n".join(lines)) from exc


def save_raw(data: dict[str, Any], path: Path | None = None) -> None:
    target = path or config.STORYBOARD
    target.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
