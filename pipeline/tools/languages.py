"""Ceiling experiment E12: can the narration be produced in other Ethiopian languages?

For each target language: translate the English lines with Gemini (stage `script`), then synthesise
with the best-matching provider/voice (stage `ceiling`). Every call goes through call_model, so
latency/failures land in runs.jsonl. Listening quality needs a native speaker; this tool only
measures what can be measured (did it work, how long, how long the audio is).
"""

from __future__ import annotations

import json

from pipeline.core import config, media
from pipeline.core.calls import call_model
from pipeline.models import Storyboard
from pipeline.providers.addis import AddisTTS
from pipeline.providers.gemini import GeminiTTS
from pipeline.stages import script

# language -> (provider, female narration-style voice)
TARGETS = {
    "om": ("addis", "om-obse"),  # Afaan Oromo, female "Narration"
    "ti": ("addis", "ti-saba"),  # Tigrinya, female "Storytelling"
    "hrr": ("gemini", "Kore"),  # Harari (Gey Sinan): no TTS provider lists it; probe Gemini
}
LINES = ("s01", "s11")


def run(sb: Storyboard) -> list[dict]:
    script.LANG_NAMES.setdefault("hrr", "Harari (Gey Sinan, the language of the city of Harar)")
    results = []
    for lang, (pname, voice) in TARGETS.items():
        row: dict = {"language": lang, "provider": pname, "voice": voice}
        try:
            tr = script.draft(sb, lang)
        except Exception as exc:  # noqa: BLE001 - record and continue with the next language
            results.append(row | {"translation": f"FAILED: {exc}"[:200]})
            continue
        prov = AddisTTS() if pname == "addis" else GeminiTTS()
        for sid in LINES:
            text = tr.get(sid, "")
            inputs = {"text": text, "language": lang, "voice": voice, "speed": 1.0, "style": None}
            item = f"{lang}_{sid}"
            try:
                out = call_model(
                    stage="ceiling",
                    item=item,
                    provider=prov.name,
                    model=prov.model,
                    inputs=inputs,
                    ext="wav",
                    run=lambda tmp, prov=prov, text=text, voice=voice, lang=lang: prov.synthesize(
                        text, tmp, voice=voice, language=lang, speed=1.0, style=None
                    ),
                )
                results.append(
                    row
                    | {
                        "shot": sid,
                        "text": text,
                        "audio": str(out.relative_to(config.ROOT)),
                        "audio_s": round(media.duration(out), 2),
                    }
                )
            except Exception as exc:  # noqa: BLE001
                results.append(row | {"shot": sid, "text": text, "error": str(exc)[:200]})
    out = config.OUTPUTS / "ceiling" / "results.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    return results
