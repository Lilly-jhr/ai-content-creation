# FAILURES: what broke, what I tried, what fixed it

Newest last. Evidence is in runs.jsonl (`status: "error"` lines) where a model call was involved.

### F1. The assignment's tooling had moved (research, 2026-11-25)
- **What:** the assignment names "Gemini 3.8 Flash TTS", FLUX.2 klein on Cloudflare and Wan 2.2 on Kaggle. I verified each before building.
- **Found:**
  - `gemini-3.8-flash-tts` exists and is free, with Amharic support.
  - klein-4B and klein-9B are both on Workers AI. 9B is non-commercial, so it is excluded.
  - **The official Wan 2.2 repo asserts FlashAttention 2, which does not run on Kaggle's T4.**
  - HunyuanVideo 1.5 needs ≥14 GB and its licence excludes the EU/UK/KR.
- **Resolution:** Wan runs through Diffusers (PyTorch SDPA attention) in fp16. Licences are recorded in ETHICS.md.

### F2. ACE-Step install: no compatible Python (2026-11-25 ~21:30)
- **What:** `uv sync` → `No interpreter found for Python >=3.11, <3.13`. The machine only has Python 3.14, and uv's managed downloads were set to manual.
- **Fix:** `uv python install 3.12`. The main pipeline is also pinned to 3.12 (`.python-version`).

### F3. ACE-Step install: torch wheel download timed out (2026-11-25 ~21:50)
- **What:** the `torch 2.10.0+cu128` wheel (~900 MB) from download-r2.pytorch.org → `operation timed out`.
- **Tried (1):** re-ran with `UV_HTTP_TIMEOUT=600` and 4 concurrent downloads. It failed again: `Connection reset by peer (os error 104)` while fetching `nvidia-cublas-cu12 12.8.4.1` (pulled in by torch cu128).
- **Tried (2):** a retry loop (6 attempts), one download at a time, `UV_HTTP_TIMEOUT=900`. uv keeps finished wheels in its cache, so each attempt resumes further along.
- **Fallback if it keeps failing:** run ACE-Step on Kaggle, where the wheels download inside Google's network.
- **Result:** fixed on the first attempt of the sequential retry loop (22:04): torch 2.10.0+cu128, `cuda.is_available() == True` on the RTX 3070 Laptop.

### F4. First assembly run: temp directory missing (2026-11-25 ~21:47)
- **What:** ffmpeg `Error opening output file …/_tmp/assemble/temp_music_96.60.wav: No such file or directory`.
- **Fix:** create the parent directory before the first write. Covered now by the rough-cut run.

### F5. End card text overflowed the vertical frame (2026-11-25 ~21:48)
- **What:** the first 9:16 render showed end-card lines cut off at both edges (Pillow draws unwrapped text).
- **Fix:** word-wrap by measured pixel width (84% of frame width). I checked by extracting the last frame.

### F6. My own secrets hook blocked my own test (2026-11-25 ~22:05)
- **What:** testing the PreToolUse hook with `echo … "git add .env" | hook.sh` was itself blocked, because the
  hook inspects the Bash command text, and that command contained `git add .env`.
- **Lesson:** the guard is live and works on the literal command. Hook tests now read their input from files.
- **Follow-up:** the deny rule `Read(./.env.*)` also blocks the agent from `.env.example` (placeholders only). I left it as is: the agent may not loosen its own guardrails. Template edits are done by the producer.

### F7. Addis AI rejected the documented request (2026-11-25 ~22:55)
- **What:** smoke test → `HTTP 422 CLIENT_REQUEST_ID_REQUIRED: client_request_id is required`. The docs listed it as optional.
- **Fix:** send `client_request_id = "alf-" + hash(request body)`. It is deterministic, so a retried request is idempotent on Addis' side and can't be billed twice. The smoke test passed after the change (runs.jsonl, stage `smoke`).

### F8. Kaggle CLI: undeclared dependency, then a changed auth model (2026-11-25 ~23:00)
- **What (1):** `kaggle kernels list` → `ModuleNotFoundError: No module named 'six'`. The current `kaggle` package imports `six` without declaring it.
- **Fix (1):** added `six` to the `kaggle` extra in pyproject.toml.
- **What (2):** the CLI no longer reads `~/.kaggle/kaggle.json`. It wants OAuth (`kaggle auth login`) or a token in `KAGGLE_API_TOKEN` / `~/.kaggle/access_token`.
- **Fix (2):** `KAGGLE_API_TOKEN` + `KAGGLE_USERNAME` go in `.env` (and as empty placeholders in `.env.example`). The pipeline loads `.env` into the process environment, so the CLI subprocess inherits the token.

### F9. Gemini free tier: 503 "high demand" on two models (2026-11-25 ~23:00 EAT)
- **What:** `gemini-3.8-flash` (translation) returned `503 UNAVAILABLE: This model is currently experiencing high demand` on 4 attempts in a row. `gemini-3.8-flash-tts` (the backup voice) did the same, 3/3, during the audition. All are logged in runs.jsonl (`status: "error"`, stages `script` and `audition`).
- **Tried:** the built-in retry/backoff (it's retryable). That wasn't enough during a demand spike.
- **Fix:** model fallback in the `script` stage: `gemini-3.8-flash` → `gemini-3.5-flash-lite` (a different cache key, also logged). Translation succeeded in 7.2 s. The audition now skips an unavailable voice instead of aborting.
- **Cost of the fix:** Flash-Lite's Amharic had visible errors (see EXPERIMENTS E2), so the fallback is only acceptable with native review.

### F10. ACE-Step weight download stalled silently (2026-11-25 22:51 → 23:10 EAT)
- **What:** the first `music` run auto-downloaded checkpoints from Hugging Face. After 92 MB it stopped growing (0 KiB in 20 s), with `.lock` files left open. No error, just a hang. The job was killed after 1112 s (logged as a `music` error).
- **Also found:** the default download pulls the **1.7B** LM. The plan for 8 GB VRAM is the **0.6B** LM.
- **Fix:** download only what we use, with `hf download` (resumable) in a retry loop: `acestep-v15-turbo/`, `vae/`, `Qwen3-Embedding-0.6B/` and the separate `ACE-Step/acestep-5Hz-lm-0.6B` repo.
- **Lesson:** my `pkill -f "pipeline music"` also matched the shell running it (exit 144). Use PIDs, not patterns.
