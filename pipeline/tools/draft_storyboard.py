"""Ceiling: a tool for a family. Plain-text story in -> a schema-valid storyboard.json draft out.

A relative writes the story in their own words (Amharic or English). Gemini drafts a storyboard
against the real JSON Schema; the result is validated with the same Pydantic models the pipeline
uses, and validation errors are fed back for up to `repairs` rounds. Every family detail comes back
flagged `pending-family`, so the draft can't silently turn into "fact". Every call is logged.
"""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from pipeline.core import config
from pipeline.core.calls import ProviderError, call_model
from pipeline.models import Storyboard
from pipeline.providers.gemini import GeminiText

SYSTEM = """You are a documentary film storyboard writer. Turn the family story you are given into a storyboard
for a 60-90 second vertical short film, as ONE JSON object that validates against the JSON Schema provided.
Rules:
- 8 to 12 shots, each 5-8 s (min_duration_s), one clear idea and one gentle movement per shot; vary shot sizes.
- Every shot states its purpose (why it exists) and emotional_beat.
- narration.text is in the requested language, short sentences written for the ear; narration.text_en is the English subtitle.
- Never invent names, dates, places or events that the story does not contain. Use role ids (e.g. "grandfather"), never real names.
- Put every family detail you use in fact_flags with status "pending-family" (the family must confirm it);
  anything you add for visuals gets status "interpretation".
- Characters: describe each visually (age, clothing, one distinctive non-sensitive detail) in a reusable description block.
- keyframe.prompt describes the still image; motion.prompt describes ONLY movement and camera (use film terms like
  push-in, crane, dolly; never the word "camera" as an object). Use seeds 1001, 1002, ...
- meta.style_block: a painterly, non-photoreal look (described by qualities, never by an artist's name).
- music: an instrumental caption suited to the story, bpm, keyscale, duration_s 95, seeds [11, 22, 33, 44].
- end_card.lines must include a "Made with AI" disclosure.
Return only the JSON object."""


def draft(story: str, language: str, title: str, repairs: int = 2) -> tuple[dict, list[str]]:
    schema = json.dumps(Storyboard.model_json_schema(), separators=(",", ":"))
    cfg = config.provider_cfg("text")
    prompt = (
        f"Language for narration.text: {language}\nTitle: {title}\n\nJSON Schema:\n{schema}\n\n"
        f"Family story:\n{story.strip()}"
    )
    history: list[str] = []
    errors: list[str] = []
    data: dict = {}
    for attempt in range(repairs + 1):
        full = (
            prompt
            if not errors
            else prompt
            + "\n\nYour previous draft failed validation:\n"
            + "\n".join(errors[:40])
            + ("\nReturn the corrected full JSON object.")
        )
        inputs = {"prompt": full, "system": SYSTEM, "language": language, "round": attempt}

        def run(tmp: Path, full=full) -> dict:
            for model in (cfg["draft_model"], cfg["model"]):
                try:
                    tmp.write_text(GeminiText(model).generate(full, system=SYSTEM, json_mode=True))
                    return {"est_cost_usd": 0.0, "model_used": model}
                except ProviderError as exc:
                    last = exc
            raise last

        out = call_model(
            stage="draft",
            item=f"{title[:20].replace(' ', '_').lower()}_r{attempt}",
            provider="gemini",
            model=cfg["draft_model"],
            inputs=inputs,
            ext="json",
            run=run,
            licence=cfg["licence"],
        )
        if out is None:
            return {}, ["dry-run"]
        text = out.read_text()
        try:
            data = json.loads(text)
            Storyboard.model_validate(data)
            history.append(f"round {attempt}: valid")
            return data, history
        except json.JSONDecodeError as exc:
            errors = [f"not valid JSON: {exc}"]
        except ValidationError as exc:
            errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        history.append(f"round {attempt}: {len(errors)} validation error(s)")
    return data, history + errors[:10]
