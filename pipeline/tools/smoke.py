"""Smoke test: one tiny call per provider, each logged to runs.jsonl with its latency."""

from __future__ import annotations

from pathlib import Path

from pipeline.core import config, runlog
from pipeline.core.calls import CTX, call_model
from pipeline.providers.addis import AddisTTS
from pipeline.providers.cloudflare import CloudflareImage
from pipeline.providers.gemini import GeminiText, GeminiTTS

AMHARIC_HELLO = "ሰላም። ይህ የድምፅ ሙከራ ነው።"  # "Hello. This is a voice test."


def _try(label: str, fn) -> None:
    try:
        out = fn()
        print(f"  OK    {label}: {out}")
    except Exception as exc:  # noqa: BLE001 - the smoke test reports every failure and moves on
        print(f"  FAIL  {label}: {type(exc).__name__}: {str(exc)[:200]}")


def _text() -> str:
    prov = GeminiText()

    def run(tmp: Path) -> dict:
        tmp.write_text(prov.generate("Reply with exactly: OK"))
        return {"est_cost_usd": 0.0}

    p = call_model(
        stage="smoke",
        item="text",
        provider=prov.name,
        model=prov.model,
        inputs={"prompt": "Reply with exactly: OK"},
        ext="txt",
        run=run,
    )
    return p.read_text().strip() if p else "dry-run"


def _tts(prov) -> str:
    inputs = {"text": AMHARIC_HELLO, "language": "am", "voice": prov.cfg["voice"], "speed": 1.0}
    p = call_model(
        stage="smoke",
        item=f"tts_{prov.name}",
        provider=prov.name,
        model=prov.model,
        inputs=inputs,
        ext="wav",
        run=lambda tmp: prov.synthesize(
            AMHARIC_HELLO, tmp, voice=inputs["voice"], language="am", speed=1.0, style=None
        ),
    )
    return str(p.relative_to(config.ROOT)) if p else "dry-run"


def _image() -> str:
    prov = CloudflareImage()
    prompt = "a small clay coffee pot (jebena) on a woven mat, painterly illustration"
    p = call_model(
        stage="smoke",
        item="image",
        provider=prov.name,
        model=prov.model,
        inputs={"prompt": prompt, "seed": 1, "width": 512, "height": 512},
        ext="png",
        run=lambda tmp: prov.generate(prompt, tmp, seed=1, width=512, height=512, refs=[]),
    )
    return str(p.relative_to(config.ROOT)) if p else "dry-run"


def _kaggle() -> str:
    from pipeline.stages.video import _kaggle as kaggle_cli

    kaggle_cli("kernels", "list", "--mine", "--page-size", "1")
    return "authenticated"


def run() -> None:
    CTX.max_attempts = 1
    print(f"smoke test, run_id={runlog.RUN_ID}")
    _try("gemini text", _text)
    _try("addis tts", lambda: _tts(AddisTTS()))
    _try("gemini tts", lambda: _tts(GeminiTTS()))
    _try("cloudflare image", _image)
    _try("kaggle cli", _kaggle)
    vendor = config.ROOT / config.provider_cfg("music")["vendor_dir"]
    print(
        f"  {'OK  ' if vendor.exists() else 'MISS'}  acestep install: {vendor.relative_to(config.ROOT)}"
    )
