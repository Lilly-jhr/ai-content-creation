"""Provenance audit: every generated asset has a sidecar and a matching runs.jsonl line."""

from __future__ import annotations

from pipeline.core import config, runlog

GENERATED_STAGES = ("narration", "refs", "keyframes", "clips", "music")


def run(warn_only: bool = False) -> int:
    logged = {r.get("input_key") for r in runlog.read() if r.get("status") == "ok"}
    problems = []
    n = 0
    for stage in GENERATED_STAGES:
        root = config.OUTPUTS / stage
        if not root.exists():
            continue
        for asset in root.rglob("*"):
            if (
                asset.is_dir()
                or asset.name.endswith(".meta.json")
                or asset.suffix in (".part", ".jsonl")
            ):
                continue
            n += 1
            if not asset.with_suffix(".meta.json").exists():
                problems.append(f"no sidecar: {asset.relative_to(config.ROOT)}")
            if asset.stem not in logged:
                problems.append(f"not in runs.jsonl: {asset.relative_to(config.ROOT)}")
    for p in problems:
        print(("WARN " if warn_only else "FAIL ") + p)
    print(f"audit: {n} assets, {len(problems)} problem(s)")
    return 0 if warn_only or not problems else 1
