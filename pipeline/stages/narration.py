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
    raw = cache.lookup(STAGE, shot.id, compute_key(STAGE, prov.name, prov.model, inputs), "wav")
    return voiced(sb, raw) if raw else None


WARMTH = "bass=g=2.5:f=160:w=0.8,treble=g=-2.5:f=7500,acompressor=threshold=-20dB:ratio=2:attack=15:release=200"


def voiced(sb: Storyboard, raw: Path) -> Path:
    """Deterministic post-processing of a TTS take (no model call): tempo + warmth.

    Addis did not reliably honour its `speed` parameter (EXPERIMENTS E1b), so tempo is applied
    here with a pitch-preserving atempo. Derived files sit next to the raw take, keyed by the
    raw key plus the processing settings, so changing them never re-bills TTS.
    """
    m = sb.meta
    if m.vo_tempo == 1.0 and not m.vo_warmth:
        return raw
    tag = f"t{m.vo_tempo:.2f}" + ("_warm" if m.vo_warmth else "")
    out = raw.with_name(f"{raw.stem}.{tag}.wav")
    if out.exists() or CTX.dry_run:
        return out if out.exists() else raw
    chain = [f"atempo={m.vo_tempo}"] if m.vo_tempo != 1.0 else []
    if m.vo_warmth:
        chain.append(WARMTH)
    media.run(["-i", str(raw), "-af", ",".join(chain), "-ar", "48000", "-ac", "1", str(out)])
    return out


def run(sb: Storyboard) -> None:
    """Generate every missing line. One failing line does not stop the others (F12)."""
    failed: dict[str, str] = {}
    for shot in sb.shots:
        if not shot.narration or not CTX.wants(shot.id):
            continue
        prov, inputs = inputs_for(sb, shot)
        try:
            _synth(prov, shot.id, inputs)
        except Exception as exc:  # noqa: BLE001 - logged in runs.jsonl; reported below
            failed[shot.id] = str(exc)[:120]
            print(f"[narration] {shot.id} failed after retries: {failed[shot.id]}")
    build_timeline(sb)
    if failed:
        raise RuntimeError(f"narration failed for {sorted(failed)}; re-run to retry only those")


def _synth(prov, shot_id: str, inputs: dict[str, Any]) -> None:
    attempts = CTX.max_attempts
    CTX.max_attempts = max(attempts, 5)  # Addis read timeouts/resets are transient (F12)
    try:
        call_model(
            stage=STAGE,
            item=shot_id,
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
    finally:
        CTX.max_attempts = attempts


def build_timeline(sb: Storyboard, verbose: bool = True) -> dict[str, Any]:
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
    if verbose:
        print(f"[timeline] total {total:.1f}s ({status}){flag}")
    return timeline
