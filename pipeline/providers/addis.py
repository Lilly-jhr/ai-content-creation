"""Addis AI text-to-speech (Addis Voices). Docs: docs.addisassistant.com/docs/capabilities/text-to-speech"""

from __future__ import annotations

import base64
from pathlib import Path
from typing import Any

from pipeline.core import media
from pipeline.core.calls import ProviderError
from pipeline.core.config import provider_cfg, secret
from pipeline.providers.base import get, post


def _find(obj: Any, *names: str) -> Any:
    """Find the first matching key anywhere in a nested JSON response."""
    if isinstance(obj, dict):
        for n in names:
            if obj.get(n):
                return obj[n]
        for v in obj.values():
            found = _find(v, *names)
            if found:
                return found
    elif isinstance(obj, list):
        for v in obj:
            found = _find(v, *names)
            if found:
                return found
    return None


class AddisTTS:
    name = "addis"

    def __init__(self) -> None:
        self.cfg = provider_cfg("tts")["addis"]
        self.model = "addis-voices"

    def _headers(self) -> dict[str, str]:
        return {"x-api-key": secret("ADDIS_API_KEY"), "Content-Type": "application/json"}

    def list_voices(self, language: str = "am") -> Any:
        url = f"{self.cfg['base_url']}/voice/voices"
        return get(url, self.name, headers=self._headers(), params={"language": language}).json()

    def synthesize(
        self, text: str, out: Path, *, voice: str, language: str, speed: float, style: str | None
    ) -> dict[str, Any]:
        body: dict[str, Any] = {
            "text": text,
            "voice_id": voice or self.cfg["voice"],
            "language": language,
            "output_format": self.cfg["output_format"],
        }
        if speed != 1.0:
            body["speed"] = speed
        url = f"{self.cfg['base_url']}/voice/generations"
        resp = post(url, self.name, headers=self._headers(), json=body)
        raw = out.with_name(out.name + ".raw")
        payload: Any
        if resp.headers.get("content-type", "").startswith("audio/"):
            raw.write_bytes(resp.content)
            payload = {"content_type": resp.headers.get("content-type")}
        else:
            payload = resp.json()
            audio_url = _find(payload, "audio_url", "url")
            b64 = _find(payload, "audio", "audio_base64")
            if audio_url:
                raw.write_bytes(get(audio_url, self.name).content)
            elif b64:
                raw.write_bytes(base64.b64decode(b64))
            else:
                keys = list(payload)[:8] if isinstance(payload, dict) else type(payload)
                raise ProviderError(f"addis: no audio in response (keys {keys})")
        try:
            media.to_wav(raw, out, sample_rate=provider_cfg("tts")["sample_rate"])
        finally:
            raw.unlink(missing_ok=True)
        seconds = media.duration(out)
        cost_etb = seconds / 60 * self.cfg["etb_per_minute"]
        safe = (
            {k: v for k, v in payload.items() if k not in ("audio", "audio_base64")}
            if isinstance(payload, dict)
            else None
        )
        return {
            "audio_s": round(seconds, 3),
            "est_cost_etb": round(cost_etb, 3),
            "est_cost_usd": round(cost_etb * self.cfg["usd_per_etb"], 5),
            "provider_response": safe,
        }
