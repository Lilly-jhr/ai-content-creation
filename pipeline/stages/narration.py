"""Stage: narration. One TTS clip per shot, then a measured timeline for the edit.

Picture is cut to the voice: each shot lasts max(min_duration_s, lead_in + narration + tail),
and the resulting timeline.json drives subtitles and assembly.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pipeline.core import cache, config, media
from pipeline.core.calls import CTX, call_model, compute_key
from pipeline.models import Shot, Storyboard
from pipeline.providers.addis import AddisTTS
from pipeline.providers.gemini import GeminiTTS
from pipeline.stages.common import write_json

STAGE = "narration"
TIMELINE = config.OUTPUTS / "timeline.json"
EST_WORDS_PER_S = 2.0  # used only for dry-run estimates before audio exists


def provider_for(name: str | None):
    name = name or config.provider_cfg("tts")["default_provider"]
    return AddisTTS() if name == "addis" else GeminiTTS()


def inputs_for(sb: Storyboard, shot: Shot) -> tuple[Any, dict[str, Any]]:
    n = shot.narration
    assert n is not None
    prov = provider_for(n.provider)
    inputs = {
        "text": n.text,
        "language": sb.meta.language,
        "voice": n.voice or prov.cfg["voice"],
        "speed": n.speed,
        "style": n.style,
    }
    return prov, inputs


def cached_clip(sb: Storyboard, shot: Shot) -> Path | None:
    if not shot.narration:
        return None
    prov, inputs = inputs_for(sb, shot)
    return cache.lookup(STAGE, shot.id, compute_key(STAGE, prov.name, prov.model, inputs), "wav")


def run(sb: Storyboard) -> None:
    for shot in sb.shots:
        if not shot.narration or not CTX.wants(shot.id):
            continue
        prov, inputs = inputs_for(sb, shot)
        call_model(
            stage=STAGE,
            item=shot.id,
            provider=prov.name,
            model=prov.model,
            inputs=inputs,
            ext="wav",
            licence=prov.cfg.get("licence", ""),
            run=lambda tmp, prov=prov, inputs=inputs: prov.synthesize(
                inputs["text"],
                tmp,
                voice=inputs["voice"],
                language=inputs["language"],
                speed=inputs["speed"],
                style=inputs["style"],
            ),
        )
    build_timeline(sb)


def build_timeline(sb: Storyboard) -> dict[str, Any]:
    m = sb.meta
    t = 0.0
    shots = []
    estimated = False
    for shot in sb.shots:
        clip = cached_clip(sb, shot)
        if clip:
            vo = media.duration(clip)
        elif shot.narration:
            vo = len(shot.narration.text.split()) / EST_WORDS_PER_S
            estimated = True
        else:
            vo = 0.0
        dur = max(shot.min_duration_s, (m.lead_in_s + vo + m.tail_s) if vo else 0.0)
        shots.append(
            {
                "id": shot.id,
                "start": round(t, 3),
                "duration": round(dur, 3),
                "vo_path": str(clip.relative_to(config.ROOT)) if clip else None,
                "vo_start": round(t + m.lead_in_s, 3) if vo else None,
                "vo_duration": round(vo, 3),
            }
        )
        t += dur
    end = {"start": round(t, 3), "duration": sb.end_card.duration_s}
    total = round(t + sb.end_card.duration_s, 3)
    timeline = {"shots": shots, "end_card": end, "total": total, "estimated": estimated}
    if not CTX.dry_run:
        write_json(TIMELINE, timeline)
    status = "ESTIMATED" if estimated else "measured"
    flag = "" if 60 <= total <= 90 else "  <-- outside the 60-90 s target"
    print(f"[timeline] total {total:.1f}s ({status}){flag}")
    return timeline
