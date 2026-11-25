"""Append-only log of every model call: runs.jsonl."""

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.core import config

RUN_ID = (
    os.environ.get("PIPELINE_RUN_ID")
    or datetime.now(UTC).strftime("%Y%m%dT%H%M%S-") + (uuid.uuid4().hex[:6])
)


def log(entry: dict[str, Any], path: Path | None = None) -> None:
    record = {"ts": datetime.now(UTC).isoformat(timespec="milliseconds"), "run_id": RUN_ID}
    record.update(entry)
    target = path or config.RUNS
    with open(target, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def read(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or config.RUNS
    if not target.exists():
        return []
    with open(target, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]
