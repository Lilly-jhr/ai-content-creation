"""Aggregate runs.jsonl into the measured tables in COSTS.md."""

from __future__ import annotations

from collections import defaultdict
from statistics import median

from pipeline.core import runlog


def summarise(records: list[dict] | None = None) -> list[dict]:
    rows: dict[tuple[str, str, str], dict] = defaultdict(
        lambda: {
            "calls": 0,
            "ok": 0,
            "errors": 0,
            "latencies": [],
            "gpu_s": 0.0,
            "usd": 0.0,
            "etb": 0.0,
        }
    )
    for r in records if records is not None else runlog.read():
        key = (r.get("stage", "?"), r.get("provider", "?"), r.get("model", "?"))
        row = rows[key]
        row["calls"] += 1
        if r.get("status") == "ok":
            row["ok"] += 1
            if r.get("latency_s") is not None:
                row["latencies"].append(float(r["latency_s"]))
        else:
            row["errors"] += 1
        row["gpu_s"] += float(r.get("gpu_s") or 0)
        row["usd"] += float(r.get("est_cost_usd") or 0)
        row["etb"] += float(r.get("est_cost_etb") or 0)
    out = []
    for (stage, provider, model), row in sorted(rows.items()):
        lat = row.pop("latencies")
        out.append(
            {
                "stage": stage,
                "provider": provider,
                "model": model,
                **row,
                "median_latency_s": round(median(lat), 2) if lat else None,
                "total_latency_s": round(sum(lat), 1),
            }
        )
    return out


def markdown() -> str:
    rows = summarise()
    lines = [
        "| Stage | Provider | Model | Calls | OK | Errors | Median latency (s) | Total latency (s) "
        "| GPU min | List-price equiv. (USD) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in rows:
        lines.append(
            f"| {r['stage']} | {r['provider']} | `{r['model']}` | {r['calls']} | {r['ok']} | {r['errors']} "
            f"| {r['median_latency_s']} | {r['total_latency_s']} | {r['gpu_s'] / 60:.1f} | {r['usd']:.4f} |"
        )
    total_usd = sum(r["usd"] for r in rows)
    total_gpu = sum(r["gpu_s"] for r in rows) / 60
    lines.append(
        f"\n**Totals:** {sum(r['calls'] for r in rows)} calls, {total_gpu:.1f} GPU-minutes, "
        f"${total_usd:.4f} list-price equivalent (actual spend: free tiers + Addis starter credit)."
    )
    return "\n".join(lines)
