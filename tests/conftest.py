from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from pipeline.core import config

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def raw_storyboard() -> dict:
    return copy.deepcopy(json.loads((ROOT / "storyboard.json").read_text()))


@pytest.fixture
def isolated_outputs(tmp_path, monkeypatch):
    """Point outputs/ and runs.jsonl at a temp dir so tests never touch real assets."""
    monkeypatch.setattr(config, "OUTPUTS", tmp_path / "outputs")
    monkeypatch.setattr(config, "RUNS", tmp_path / "runs.jsonl")
    from pipeline.core import calls

    monkeypatch.setattr(calls, "CTX", calls.RunContext(base_backoff_s=0.0))
    return tmp_path
