# CLAUDE.md: working agreement for coding agents in this repo

This repo is a storyboard-driven film pipeline for the heritage short *A Little Further*.
`storyboard.json` is the contract. Every stage reads it and writes only its own outputs.

## Commands
- `make check`: ruff + pytest (run after any change to `pipeline/`)
- `make validate`: validate the storyboard (a hook also runs this after edits to it)
- `make dry-run`: what would be generated vs reused, and which field changed
- `make film`: the full pipeline. **Generation stages spend quota, so ask the producer before running them.**
- `python -m pipeline schema` after editing `pipeline/models.py`; the schema-drift test enforces this.

## Rules
1. **Every model call goes through `pipeline.core.calls.call_model()`** (or `register_external` for Kaggle).
   Never call a provider directly from a stage. That function owns caching, retries, `runs.jsonl` and sidecars.
2. **Cache keys contain exactly what the asset depends on.** If you add a parameter that changes the
   output, it must be in the stage's `inputs_for()`; if it doesn't change the output, it must not be.
3. Prompts, seeds and parameters live in `storyboard.json` or `config/providers.toml`, never hidden in code.
4. **Never invent family history.** Any new detail about a real person gets a `fact_flags` entry:
   `family-confirmed`, `researched` (with source), `interpretation`, or `pending-family`.
   Check visual claims about Harar against `docs/research/harar-brief.md`.
5. **Privacy:** prompts use role ids (`mother`, `gen1_tailor_m`), never real names or private details.
   Free-tier endpoints may train on inputs.
6. **Secrets:** only in `.env` (never read, print or commit it). `kaggle.json` lives in `~/.kaggle/`.
7. **Consent:** nothing depicting or voicing a real person is generated before ETHICS.md has their consent record.
8. **Approvals are data:** downstream stages use only assets whose key is in `approved_key`.
   Don't approve assets on the producer's behalf.
9. Delivery specs: 60–90 s, 9:16 (1080×1920) and 16:9 (1920×1080), 24 fps CFR, H.264/AAC,
   −14 LUFS integrated / ≤ −1 dBTP, subtitles ≤ 2 lines × 40 chars inside the safe area, AI end card.
10. When something breaks, add an entry to FAILURES.md (what broke, what you tried, what fixed it).
    When you compare two settings, add an EXPERIMENTS.md entry with evidence (runs.jsonl keys).

## Layout
`pipeline/core` (cache, calls, runlog, config, media) · `pipeline/providers` (one file per external service)
· `pipeline/stages` (narration → subtitles → refs → keyframes → video → music → assemble)
· `kaggle/wan_i2v` (GPU kernel) · `music/acestep_job.py` (runs inside the ACE-Step env).
