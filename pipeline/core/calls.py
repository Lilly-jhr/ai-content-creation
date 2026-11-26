"""The single choke point for model calls: cache lookup -> retries -> runs.jsonl -> sidecar.

Stages never call providers directly; they call `call_model()` with the exact inputs
the asset depends on. The cache key is a hash of those inputs, so changing one shot's
prompt changes only that shot's key, and only that asset is regenerated.
"""

from __future__ import annotations

import random
import re
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pipeline.core import cache, runlog
from pipeline.core.config import MissingCredentials
from pipeline.core.hashing import hash_obj

_URL_QUERY = re.compile(r"(https?://[^\s?'\"]+)\?[^\s'\"]*")


def sanitize(text: str) -> str:
    """Strip URL query strings (signed URLs look like tokens) and the local home path from log text."""
    return _URL_QUERY.sub(r"\1?<redacted>", text).replace(str(Path.home()), "~")


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, retry_after: float | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.retry_after = retry_after


@dataclass
class RunContext:
    dry_run: bool = False
    force: bool = False
    allow_draft: bool = False
    shots: set[str] | None = None
    max_attempts: int = 3
    base_backoff_s: float = 2.0
    plan: list[dict[str, Any]] = field(default_factory=list)
    reused: int = 0
    generated: int = 0

    def wants(self, shot_id: str) -> bool:
        return self.shots is None or shot_id in self.shots


CTX = RunContext()


def compute_key(stage: str, provider: str, model: str, inputs: dict[str, Any]) -> str:
    return hash_obj({"stage": stage, "provider": provider, "model": model, "inputs": inputs})


def call_model(
    *,
    stage: str,
    item: str,
    provider: str,
    model: str,
    inputs: dict[str, Any],
    ext: str,
    run: Callable[[Path], dict[str, Any] | None],
    licence: str = "",
) -> Path | None:
    """Return the asset path for these inputs, generating it only if it is not cached.

    `run(tmp_path)` must write the asset to tmp_path and may return extra log fields
    (e.g. est_cost_usd, gpu_s, provider_response). Returns None only in dry-run mode
    when the asset would be generated.
    """
    key = compute_key(stage, provider, model, inputs)
    cached = cache.lookup(stage, item, key, ext)
    if cached and not CTX.force:
        if CTX.dry_run:
            CTX.plan.append({"stage": stage, "item": item, "action": "reuse", "key": key})
        CTX.reused += 1
        return cached

    if CTX.dry_run:
        changed = cache.changed_fields(cache.latest_meta(stage, item), inputs)
        CTX.plan.append(
            {"stage": stage, "item": item, "action": "generate", "key": key, "changed": changed}
        )
        return None

    out = cache.asset_path(stage, item, key, ext)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".part")
    base = {
        "stage": stage,
        "shot_id": item,
        "provider": provider,
        "model": model,
        "prompt": inputs.get("prompt") or inputs.get("text") or inputs.get("caption"),
        "params": {k: v for k, v in inputs.items() if k not in ("prompt", "text", "caption")},
        "seed": inputs.get("seed"),
        "input_key": key,
    }

    for attempt in range(1, CTX.max_attempts + 1):
        t0 = time.perf_counter()
        try:
            extra = run(tmp) or {}
            if not tmp.exists() or tmp.stat().st_size == 0:
                raise ProviderError("provider returned no data", retryable=True)
            shutil.move(tmp, out)
            CTX.generated += 1
            latency = round(time.perf_counter() - t0, 3)
            entry = base | {
                "status": "ok",
                "attempt": attempt,
                "latency_s": latency,
                "output_path": str(out.relative_to(cache.asset_dir(stage, item).parents[1])),
            }
            entry.update({k: v for k, v in extra.items() if k != "provider_response"})
            runlog.log(entry)
            cache.write_meta(
                out,
                {
                    "key": key,
                    "stage": stage,
                    "item": item,
                    "provider": provider,
                    "model": model,
                    "inputs": inputs,
                    "run_id": runlog.RUN_ID,
                    "latency_s": latency,
                    "licence": licence,
                    "provider_response": extra.get("provider_response"),
                },
            )
            return out
        except MissingCredentials:
            raise
        except Exception as exc:  # noqa: BLE001 - every failure is logged, then re-raised or retried
            latency = round(time.perf_counter() - t0, 3)
            retryable = isinstance(exc, ProviderError) and exc.retryable
            runlog.log(
                base
                | {
                    "status": "error",
                    "attempt": attempt,
                    "latency_s": latency,
                    "error": sanitize(f"{type(exc).__name__}: {exc}")[:500],
                    "retryable": retryable,
                }
            )
            tmp.unlink(missing_ok=True)
            if not retryable or attempt == CTX.max_attempts:
                raise
            wait = getattr(exc, "retry_after", None) or CTX.base_backoff_s * 2 ** (attempt - 1)
            time.sleep(wait + random.uniform(0, 0.5))
    raise AssertionError("unreachable")


def register_external(
    *,
    stage: str,
    item: str,
    provider: str,
    model: str,
    inputs: dict[str, Any],
    ext: str,
    src: Path,
    log_fields: dict[str, Any],
    licence: str = "",
) -> Path:
    """Register an asset produced outside this process (e.g. a Kaggle GPU job) into the cache."""
    key = compute_key(stage, provider, model, inputs)
    out = cache.asset_path(stage, item, key, ext)
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, out)
    runlog.log(
        {
            "stage": stage,
            "shot_id": item,
            "provider": provider,
            "model": model,
            "prompt": inputs.get("prompt"),
            "params": {k: v for k, v in inputs.items() if k != "prompt"},
            "seed": inputs.get("seed"),
            "input_key": key,
            "status": "ok",
            "attempt": 1,
            "output_path": f"{stage}/{item}/{out.name}",
        }
        | log_fields
    )
    cache.write_meta(
        out,
        {
            "key": key,
            "stage": stage,
            "item": item,
            "provider": provider,
            "model": model,
            "inputs": inputs,
            "run_id": runlog.RUN_ID,
            "licence": licence,
        }
        | {"external": log_fields},
    )
    return out
