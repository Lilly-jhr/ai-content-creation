"""Stage: script. Drafts the narration translation (English -> meta.language) with Gemini.

One call translates every line together so terminology and voice stay consistent. The
result is a DRAFT: `translate --apply` writes it into storyboard narration.text, and a
native speaker reviews it before the narration is approved (DESIGN.md / FAILURES.md).
Only narration text is sent, never names or private details.
"""

from __future__ import annotations

import json
from pathlib import Path

from pipeline.core import config
from pipeline.core.calls import ProviderError, call_model
from pipeline.models import Storyboard
from pipeline.providers.gemini import GeminiText
from pipeline.stages import common

STAGE = "script"
LANG_NAMES = {"am": "Amharic", "om": "Afaan Oromo", "ti": "Tigrinya", "so": "Somali"}

SYSTEM = (
    "You translate documentary film narration for voice-over. Write natural, spoken {lang} in its "
    "native script (no transliteration), for a young woman narrating in the first person about her own "
    "family. Use short sentences written for the ear, warm and simple, never bureaucratic. Keep the "
    "meaning of each line exactly; do not add facts, names, places or dates. Keep 'Harar' as the city name. "
    "'My' must stay possessive (my mother, my great-grandparents). "
    "Return only a JSON object mapping each line id to its translation."
)
# Terms the first (Flash-Lite) draft got wrong; see EXPERIMENTS E2.
GLOSSARY = {"am": {"tailors": "ልብስ ሰፊዎች", "my mother": "እናቴ", "merchants": "ነጋዴዎች"}}


def draft(sb: Storyboard, language: str | None = None, model: str | None = None) -> dict[str, str]:
    lang = language or sb.meta.language
    lines = {s.id: s.narration.text_en for s in sb.shots if s.narration}
    system = SYSTEM.format(lang=LANG_NAMES.get(lang, lang))
    glossary = GLOSSARY.get(lang)
    prompt = "Translate these narration lines:\n" + json.dumps(lines, ensure_ascii=False, indent=1)
    if glossary:
        prompt += "\nUse this glossary:\n" + json.dumps(glossary, ensure_ascii=False)
    inputs = {"prompt": prompt, "system": system, "language": lang}
    cfg = config.provider_cfg("text")
    if model:  # explicit model: no fallback, so drafts from different models can be compared (E2)
        cfg = {**cfg, "draft_model": model, "model": model}

    def attempt(model: str) -> Path | None:
        prov = GeminiText(model)

        def run(tmp: Path) -> dict:
            parsed = json.loads(prov.generate(prompt, system=system, json_mode=True))
            missing = set(lines) - set(parsed)
            if missing:
                raise ValueError(f"translation missing lines {sorted(missing)}")
            tmp.write_text(json.dumps(parsed, ensure_ascii=False, indent=2))
            return {"est_cost_usd": 0.0, "n_lines": len(parsed)}

        return call_model(
            stage=STAGE,
            item=f"translation_{lang}",
            provider=prov.name,
            model=model,
            inputs=inputs,
            ext="json",
            run=run,
            licence=cfg["licence"],
        )

    try:
        out = attempt(cfg["draft_model"])
    except ProviderError as exc:  # e.g. 503 "high demand" on the larger free model
        print(
            f"[script] {cfg['draft_model']} unavailable ({str(exc)[:60]}...); falling back to {cfg['model']}"
        )
        out = attempt(cfg["model"])
    return json.loads(out.read_text()) if out else {}


def apply(translations: dict[str, str]) -> int:
    raw = common.load_raw()
    n = 0
    for shot in raw["shots"]:
        nar = shot.get("narration")
        if nar and shot["id"] in translations:
            nar["text"] = translations[shot["id"]]
            n += 1
    common.save_raw(raw)
    common.load()  # re-validate
    return n
