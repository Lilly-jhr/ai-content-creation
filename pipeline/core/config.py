"""Paths, secrets (from .env) and provider configuration (config/providers.toml)."""

from __future__ import annotations

import os
import tomllib
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
OUTPUTS = ROOT / "outputs"
STORYBOARD = ROOT / "storyboard.json"
SCHEMA = ROOT / "schema" / "storyboard.schema.json"
RUNS = ROOT / "runs.jsonl"
FONTS = ROOT / "fonts"

load_dotenv(ROOT / ".env")


class MissingCredentials(RuntimeError):
    """Raised when a stage needs to call a provider but its key is not configured."""


def secret(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise MissingCredentials(
            f"{name} is not set. Copy .env.example to .env and fill it in, "
            "or run with cached outputs only (all cache hits need no keys)."
        )
    return value


@lru_cache
def providers() -> dict:
    with open(ROOT / "config" / "providers.toml", "rb") as f:
        return tomllib.load(f)


def provider_cfg(section: str) -> dict:
    return providers()[section]
