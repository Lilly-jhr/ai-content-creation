"""Stage: music. ACE-Step 1.5 score candidates, run locally on the GPU in an isolated env.

Each seed in storyboard.music.seeds is one cached candidate. The chosen one
(music.chosen_seed, with music.why) is what assembly uses.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from pipeline.core import cache, config
from pipeline.core.calls import ProviderError, call_model, compute_key
from pipeline.models import Storyboard

STAGE = "music"
JOB_DIR = config.OUTPUTS / "_tmp" / "music_jobs"


def _cfg() -> dict[str, Any]:
    return config.provider_cfg("music")


def inputs_for(sb: Storyboard, seed: int) -> dict[str, Any]:
    m = sb.music
    return {
        "caption": m.caption,
        "lyrics": m.lyrics,
        "bpm": m.bpm,
        "keyscale": m.keyscale,
        "timesignature": m.timesignature,
        "duration_s": m.duration_s,
        "seed": seed,
    }


def candidate_path(sb: Storyboard, seed: int) -> Path | None:
    c = _cfg()
    return cache.lookup(
        STAGE, "score", compute_key(STAGE, c["provider"], c["model"], inputs_for(sb, seed)), "wav"
    )


def chosen_path(sb: Storyboard) -> Path | None:
    return candidate_path(sb, sb.music.chosen_seed) if sb.music.chosen_seed is not None else None


def _run_acestep(inputs: dict[str, Any], tmp: Path) -> dict[str, Any]:
    c = _cfg()
    vendor = config.ROOT / c["vendor_dir"]
    if not vendor.exists():
        raise config.MissingCredentials(
            f"ACE-Step not installed at {c['vendor_dir']}; run `make music-setup` (or use cached music)"
        )
    JOB_DIR.mkdir(parents=True, exist_ok=True)
    job = JOB_DIR / f"{inputs['seed']}.json"
    # offload: 8 GB laptop GPU cannot hold DiT + LM + embedder + VAE at once (F19); execution-only, not in the key
    job.write_text(json.dumps(inputs | {"vendor_dir": str(vendor), "offload": True}))
    wav = tmp.with_name(tmp.name + ".wav")
    # Call the vendor venv's interpreter directly: `uv run --project` re-syncs the env first,
    # which on this network meant another timed-out wheel download (FAILURES F18).
    py = vendor / ".venv" / "bin" / "python"
    cmd = (
        [str(py)] if py.exists() else ["uv", "run", "--no-sync", "--project", str(vendor), "python"]
    )
    proc = subprocess.run(
        [*cmd, str(config.ROOT / "music" / "acestep_job.py"), str(job), str(wav)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise ProviderError(f"acestep failed: {proc.stderr[-800:]}")
    stats = json.loads(proc.stdout.strip().splitlines()[-1])
    wav.replace(tmp)
    gpu_s = stats["gen_s"] + stats["load_s"]
    return {
        "gpu_s": round(gpu_s, 2),
        "gen_s": stats["gen_s"],
        "gpu": stats["gpu"],
        "peak_vram_gb": stats["peak_vram_gb"],
        "est_cost_usd": round(gpu_s / 3600 * c["usd_per_gpu_hour_list"], 5),
        "provider_response": stats,
    }


def run(sb: Storyboard) -> None:
    c = _cfg()
    for seed in sb.music.seeds:
        inputs = inputs_for(sb, seed)
        call_model(
            stage=STAGE,
            item="score",
            provider=c["provider"],
            model=c["model"],
            inputs=inputs,
            ext="wav",
            licence=c["licence"],
            run=lambda tmp, inputs=inputs: _run_acestep(inputs, tmp),
        )
