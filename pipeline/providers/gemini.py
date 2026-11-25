"""Gemini API: text generation and text-to-speech (REST generateContent)."""

from __future__ import annotations

import base64
import wave
from pathlib import Path
from typing import Any

from pipeline.core import media
from pipeline.core.calls import ProviderError
from pipeline.core.config import provider_cfg, secret
from pipeline.providers.base import post

API = "https://generativelanguage.googleapis.com/v1beta/models"


def _generate(model: str, body: dict[str, Any]) -> dict[str, Any]:
    headers = {"x-goog-api-key": secret("GEMINI_API_KEY"), "Content-Type": "application/json"}
    return post(f"{API}/{model}:generateContent", "gemini", headers=headers, json=body).json()


def _parts(resp: dict[str, Any]) -> list[dict[str, Any]]:
    try:
        return resp["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError) as exc:
        reason = resp.get("promptFeedback") or resp.get("candidates", [{}])[0].get("finishReason")
        raise ProviderError(f"gemini: empty response ({reason})", retryable=True) from exc


class GeminiText:
    name = "gemini"

    def __init__(self, model: str | None = None) -> None:
        self.model = model or provider_cfg("text")["model"]

    def generate(self, prompt: str, *, system: str | None = None, json_mode: bool = False) -> str:
        body: dict[str, Any] = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        if system:
            body["systemInstruction"] = {"parts": [{"text": system}]}
        if json_mode:
            body["generationConfig"] = {"responseMimeType": "application/json"}
        return "".join(p.get("text", "") for p in _parts(_generate(self.model, body)))


class GeminiTTS:
    name = "gemini"

    def __init__(self) -> None:
        self.cfg = provider_cfg("tts")["gemini"]
        self.model = self.cfg["model"]

    def synthesize(
        self, text: str, out: Path, *, voice: str, language: str, speed: float, style: str | None
    ) -> dict[str, Any]:
        spoken = f"{style}:\n{text}" if style else text
        voice_cfg = {"prebuiltVoiceConfig": {"voiceName": voice or self.cfg["voice"]}}
        body = {
            "contents": [{"role": "user", "parts": [{"text": spoken}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {"voiceConfig": voice_cfg},
            },
        }
        parts = _parts(_generate(self.model, body))
        inline = next((p["inlineData"] for p in parts if "inlineData" in p), None)
        if not inline:
            raise ProviderError("gemini tts: no audio part in response", retryable=True)
        pcm = base64.b64decode(inline["data"])
        mime = inline.get("mimeType", "")
        rate = int(mime.split("rate=")[1].split(";")[0]) if "rate=" in mime else 24000
        raw = out.with_name(out.name + ".raw.wav")
        with wave.open(str(raw), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(rate)
            w.writeframes(pcm)
        try:
            if speed != 1.0:
                tmp = raw.with_name(raw.name + ".tempo.wav")
                media.run(["-i", str(raw), "-af", f"atempo={speed}", str(tmp)])
                tmp.replace(raw)
            media.to_wav(raw, out, sample_rate=provider_cfg("tts")["sample_rate"])
        finally:
            raw.unlink(missing_ok=True)
        return {"audio_s": round(media.duration(out), 3), "est_cost_usd": 0.0, "source_mime": mime}
