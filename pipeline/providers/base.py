"""Provider interfaces. Model-specific request/response logic stays inside implementations."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

import requests

from pipeline.core.calls import ProviderError

TIMEOUT = (10, 180)


class TTSProvider(Protocol):
    name: str
    model: str

    def synthesize(
        self, text: str, out: Path, *, voice: str, language: str, speed: float, style: str | None
    ) -> dict[str, Any]: ...


class ImageProvider(Protocol):
    name: str
    model: str

    def generate(
        self, prompt: str, out: Path, *, seed: int, width: int, height: int, refs: list[Path]
    ) -> dict[str, Any]: ...


class TextProvider(Protocol):
    name: str
    model: str

    def generate(
        self, prompt: str, *, system: str | None = None, json_mode: bool = False
    ) -> str: ...


class MusicProvider(Protocol):
    name: str
    model: str

    def generate(self, job: dict[str, Any], out_dir: Path) -> dict[str, Any]: ...


def check_response(resp: requests.Response, provider: str) -> requests.Response:
    """Map HTTP errors to retryable / non-retryable ProviderErrors."""
    if resp.ok:
        return resp
    retry_after = resp.headers.get("Retry-After")
    body = resp.text[:300].replace("\n", " ")
    retryable = resp.status_code in (408, 409, 425, 429) or resp.status_code >= 500
    raise ProviderError(
        f"{provider} HTTP {resp.status_code}: {body}",
        retryable=retryable,
        retry_after=float(retry_after) if retry_after and retry_after.isdigit() else None,
    )


def post(url: str, provider: str, **kwargs: Any) -> requests.Response:
    try:
        resp = requests.post(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise ProviderError(f"{provider} network error: {exc}", retryable=True) from exc
    return check_response(resp, provider)


def get(url: str, provider: str, **kwargs: Any) -> requests.Response:
    try:
        resp = requests.get(url, timeout=kwargs.pop("timeout", TIMEOUT), **kwargs)
    except (requests.ConnectionError, requests.Timeout) as exc:
        raise ProviderError(f"{provider} network error: {exc}", retryable=True) from exc
    return check_response(resp, provider)
