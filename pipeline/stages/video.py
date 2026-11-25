"""Stage: video. Wan 2.2 TI2V-5B image-to-video on a Kaggle GPU, asynchronously.

`submit` bundles approved keyframes + motion prompts into a Kaggle dataset and pushes the
kernel in kaggle/wan_i2v. `fetch` downloads finished clips and registers each in the cache
under the exact inputs that were submitted. Assembly uses a clip only if one is cached for
the current inputs; otherwise it falls back to Ken Burns, so GPU problems never block the film.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pipeline.core import cache, config, runlog
from pipeline.core.calls import CTX, compute_key, register_external
from pipeline.core.hashing import hash_file
from pipeline.models import Shot, Storyboard
from pipeline.stages import keyframes as kf_stage

STAGE = "clips"
PROVIDER = "kaggle"
KERNEL_DIR = config.ROOT / "kaggle" / "wan_i2v"
BUNDLE = config.OUTPUTS / "_tmp" / "kaggle_bundle"
DOWNLOAD = config.OUTPUTS / "_tmp" / "kaggle_out"
SUBMISSIONS = config.OUTPUTS / STAGE / "submissions.jsonl"


def _cfg() -> dict[str, Any]:
    return config.provider_cfg("video")


def inputs_for(sb: Storyboard, shot: Shot, ratio: str) -> dict[str, Any] | None:
    kf = kf_stage.current_path(sb, shot, require_approved=True)
    if kf is None:
        return None
    c = _cfg()
    return {
        "prompt": shot.motion.prompt,
        "seed": shot.motion.seed,
        "keyframe": hash_file(kf),
        "ratio": ratio,
        "width": c[f"width_{ratio}"],
        "height": c[f"height_{ratio}"],
        "frames": shot.motion.frames,
        "steps": shot.motion.steps,
        "fps": c["fps"],
    }


def cached_clip(sb: Storyboard, shot: Shot, ratio: str) -> Path | None:
    inputs = inputs_for(sb, shot, ratio)
    if inputs is None:
        return None
    return cache.lookup(
        STAGE, shot.id, compute_key(STAGE, PROVIDER, _cfg()["model"], inputs), "mp4"
    )


def pending_jobs(sb: Storyboard) -> list[dict[str, Any]]:
    jobs = []
    for shot in sb.shots:
        if (
            shot.motion.mode not in ("auto", "wan")
            or not shot.motion.prompt
            or not CTX.wants(shot.id)
        ):
            continue
        for ratio in shot.motion.targets:
            inputs = inputs_for(sb, shot, ratio)
            if inputs is None:
                print(f"[video] {shot.id}: keyframe not approved, skipping")
                continue
            key = compute_key(STAGE, PROVIDER, _cfg()["model"], inputs)
            if cache.lookup(STAGE, shot.id, key, "mp4") and not CTX.force:
                CTX.plan.append({"stage": STAGE, "item": shot.id, "action": "reuse", "key": key})
                continue
            jobs.append(
                {
                    "key": key,
                    "shot": shot.id,
                    "inputs": inputs,
                    "keyframe_path": str(kf_stage.current_path(sb, shot)),
                }
            )
    return jobs


def _kaggle(*args: str) -> str:
    exe = shutil.which("kaggle")
    cmd = [exe, *args] if exe else ["uv", "run", "--extra", "kaggle", "kaggle", *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, cwd=config.ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"kaggle {' '.join(args)} failed: {proc.stderr or proc.stdout}")
    return proc.stdout


def _username() -> str:
    user = os.environ.get("KAGGLE_USERNAME")
    if user:
        return user
    cred = Path.home() / ".kaggle" / "kaggle.json"
    if cred.exists():
        return json.loads(cred.read_text())["username"]
    raise config.MissingCredentials("Kaggle credentials missing: put kaggle.json in ~/.kaggle/")


def submit(sb: Storyboard, limit: int | None = None) -> list[dict[str, Any]]:
    jobs = pending_jobs(sb)[:limit] if limit else pending_jobs(sb)
    if CTX.dry_run:
        for j in jobs:
            CTX.plan.append(
                {"stage": STAGE, "item": j["shot"], "action": "generate (kaggle)", "key": j["key"]}
            )
        return jobs
    if not jobs:
        print("[video] nothing to submit: every requested clip is cached")
        return jobs
    user = _username()
    shutil.rmtree(BUNDLE, ignore_errors=True)
    BUNDLE.mkdir(parents=True)
    manifest = []
    for j in jobs:
        img = f"{j['shot']}_{j['key']}.png"
        shutil.copyfile(j["keyframe_path"], BUNDLE / img)
        manifest.append({"key": j["key"], "shot": j["shot"], "image": img, **j["inputs"]})
    (BUNDLE / "jobs.json").write_text(json.dumps(manifest, indent=2))
    dataset = f"{user}/alf-wan-jobs"
    (BUNDLE / "dataset-metadata.json").write_text(
        json.dumps({"title": "alf-wan-jobs", "id": dataset, "licenses": [{"name": "other"}]})
    )
    try:
        _kaggle(
            "datasets",
            "version",
            "-p",
            str(BUNDLE),
            "-m",
            f"jobs {runlog.RUN_ID}",
            "--dir-mode",
            "zip",
        )
    except RuntimeError:
        _kaggle("datasets", "create", "-p", str(BUNDLE), "--dir-mode", "zip")
    meta = json.loads((KERNEL_DIR / "kernel-metadata.json").read_text())
    meta["id"] = f"{user}/alf-wan-i2v"
    meta["dataset_sources"] = [dataset]
    (KERNEL_DIR / "kernel-metadata.json").write_text(json.dumps(meta, indent=2) + "\n")
    _kaggle("kernels", "push", "-p", str(KERNEL_DIR))
    SUBMISSIONS.parent.mkdir(parents=True, exist_ok=True)
    with open(SUBMISSIONS, "a") as f:
        f.write(
            json.dumps(
                {
                    "ts": datetime.now(UTC).isoformat(),
                    "run_id": runlog.RUN_ID,
                    "kernel": meta["id"],
                    "jobs": manifest,
                }
            )
            + "\n"
        )
    print(f"[video] submitted {len(jobs)} clip job(s) to Kaggle kernel {meta['id']}")
    return jobs


def status() -> str:
    return _kaggle("kernels", "status", f"{_username()}/alf-wan-i2v").strip()


def fetch() -> int:
    """Download kernel output and register every finished clip under its submitted inputs."""
    if CTX.dry_run:
        return 0
    user = _username()
    shutil.rmtree(DOWNLOAD, ignore_errors=True)
    DOWNLOAD.mkdir(parents=True)
    _kaggle("kernels", "output", f"{user}/alf-wan-i2v", "-p", str(DOWNLOAD))
    results_file = next(DOWNLOAD.rglob("results.json"), None)
    if not results_file:
        print("[video] no results.json in kernel output yet")
        return 0
    results = json.loads(results_file.read_text())
    c = _cfg()
    n = 0
    for r in results:
        inputs = {
            k: r[k]
            for k in (
                "prompt",
                "seed",
                "keyframe",
                "ratio",
                "width",
                "height",
                "frames",
                "steps",
                "fps",
            )
        }
        if r.get("status") != "ok":
            runlog.log(
                {
                    "stage": STAGE,
                    "shot_id": r["shot"],
                    "provider": PROVIDER,
                    "model": c["model"],
                    "prompt": r["prompt"],
                    "seed": r["seed"],
                    "input_key": r["key"],
                    "status": "error",
                    "attempt": 1,
                    "error": r.get("error"),
                    "gpu_s": r.get("gpu_s"),
                    "gpu": r.get("gpu"),
                }
            )
            continue
        src = next(DOWNLOAD.rglob(r["file"]))
        gpu_s = float(r.get("gpu_s", 0))
        register_external(
            stage=STAGE,
            item=r["shot"],
            provider=PROVIDER,
            model=c["model"],
            inputs=inputs,
            ext="mp4",
            src=src,
            licence=c["licence"],
            log_fields={
                "latency_s": gpu_s,
                "gpu_s": gpu_s,
                "gpu": r.get("gpu"),
                "dtype": r.get("dtype"),
                "peak_vram_gb": r.get("peak_vram_gb"),
                "est_cost_usd": round(gpu_s / 3600 * c["usd_per_gpu_hour_list"], 4),
            },
        )
        n += 1
    print(f"[video] registered {n} clip(s)")
    return n
