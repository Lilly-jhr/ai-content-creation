"""Runs INSIDE the ACE-Step 1.5 uv environment (vendor/ACE-Step-1.5).

Usage: uv run --project vendor/ACE-Step-1.5 python music/acestep_job.py job.json out.wav
Prints one JSON line with timing/VRAM so the main pipeline can log it to runs.jsonl.
Kept separate so torch/CUDA dependencies never touch the main pipeline environment.
"""

import json
import os
import shutil
import sys
import time
from pathlib import Path

import torch
from acestep.handler import AceStepHandler
from acestep.inference import GenerationConfig, GenerationParams, generate_music
from acestep.llm_inference import LLMHandler
from acestep.model_downloader import ensure_lm_model, ensure_main_model, get_checkpoints_dir

job = json.loads(Path(sys.argv[1]).read_text())
out = Path(sys.argv[2])
vendor = Path(job["vendor_dir"]).resolve()
os.chdir(vendor)

t0 = time.perf_counter()
ckpt = get_checkpoints_dir()
# ACE-Step's ensure_main_model() also demands the 1.7B LM, which we do not use (8 GB VRAM -> 0.6B LM);
# on this network it would trigger another multi-GB download (FAILURES F10). Check only what we load.
for part in ("acestep-v15-turbo", "vae", "Qwen3-Embedding-0.6B"):
    if not any((ckpt / part).glob("*.safetensors")):
        ensure_main_model(ckpt)
        break
# initialize_service() re-checks the "main model", which includes the 1.7B LM we never load, and
# would start a multi-GB download through mirrors this network can't resolve (FAILURES F18).
# We verified above that every component we actually load is present.
import acestep.core.generation.handler.init_service_downloads as _isd  # noqa: E402

_isd.check_main_model_exists = lambda *a, **k: True
lm_name = job.get("lm_model", "acestep-5Hz-lm-0.6B")
use_lm = job.get("use_lm", True)
if use_lm:
    ensure_lm_model(lm_name, ckpt)
t_dl = time.perf_counter() - t0

dit = AceStepHandler()
msg, ok = dit.initialize_service(
    project_root=str(vendor),
    config_path=job.get("dit_config", "acestep-v15-turbo"),
    device="cuda",
    offload_to_cpu=job.get("offload", False),
)
if not ok:
    raise SystemExit(f"DiT init failed: {msg}")
llm = LLMHandler()
if use_lm:
    msg, ok = llm.initialize(
        checkpoint_dir=str(ckpt),
        lm_model_path=lm_name,
        backend="pt",
        device="cuda",
        offload_to_cpu=job.get("offload", False),
    )
    if not ok:
        raise SystemExit(f"LM init failed: {msg}")
t_load = time.perf_counter() - t0 - t_dl

torch.cuda.reset_peak_memory_stats()
t1 = time.perf_counter()
params = GenerationParams(
    caption=job["caption"],
    lyrics=job.get("lyrics", "[Instrumental]"),
    instrumental=True,
    bpm=job.get("bpm"),
    keyscale=job.get("keyscale") or "",
    timesignature=job.get("timesignature") or "",
    duration=float(job["duration_s"]),
    seed=int(job["seed"]),
    thinking=use_lm,
)
config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(job["seed"])], audio_format="wav")
tmp_dir = out.parent / (out.name + ".d")
result = generate_music(dit, llm, params, config, save_dir=str(tmp_dir))
gen_s = time.perf_counter() - t1
if not result.success:
    raise SystemExit(f"generation failed: {result.error}")
src = Path(result.audios[0]["path"])
shutil.move(str(src), out)
shutil.rmtree(tmp_dir, ignore_errors=True)
print(
    json.dumps(
        {
            "gen_s": round(gen_s, 2),
            "load_s": round(t_load, 2),
            "download_s": round(t_dl, 2),
            "gpu": torch.cuda.get_device_name(0),
            "peak_vram_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
            "lm_metadata": {
                k: v
                for k, v in (result.extra_outputs.get("lm_metadata") or {}).items()
                if isinstance(v, (str, int, float))
            },
        }
    )
)
