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

### F11. Addis TTS `speed` parameter silently ignored (2026-11-25 ~23:55 EAT)
- **What:** after the testers asked for a slower, warmer voice, `speed=0.85` returned a clip the same length as `speed=1.0` (5.30 s vs 5.29 s). There was no error. Addis also documents that `style` is accepted but ignored.
- **Fix:** the slow-down and warmth are now a deterministic FFmpeg post-process in our own narration stage (EXPERIMENTS E1b). The provider only supplies the take.
- **Lesson:** an accepted parameter isn't necessarily an honoured one. Measure the output.

### F12. Addis API read timeouts and connection resets mid-run (2026-11-25 ~23:58 EAT)
- **What:** in the first full narration run, s01 and s07 timed out once each (`Read timed out`, 180 s and 227 s; one was on the CDN audio download). s09 failed **3/3** (a read timeout, then a timeout, then `Connection reset by peer`). The stage raised on s09, so **s10–s11 and the radio cut were never produced**. Everything is in runs.jsonl.
- **Fix:** (1) narration now continues past a failed line and reports all failures at the end, so one bad line can't block the rest. (2) It allows 5 attempts for TTS. (3) Re-running only retries the missing lines, because the others are cached.
- **Result:** the re-run regenerated only the 7 changed or missing lines (s06 needed 3 attempts). The radio cut rendered at 89.5 s.

### F13. True peak over the ceiling after AAC encoding (2026-11-26 00:51 EAT)
- **What:** the radio cut measured −14.0 LUFS (on target) but a true peak of **−0.6 dBTP**, above the −1 dBTP spec. `loudnorm` in linear mode doesn't guarantee the peak, and AAC encoding overshoots.
- **Fix:** a 4×-oversampled `alimiter` (limit 0.83 ≈ −1.6 dBFS) after the second loudnorm pass. Re-measured: **−14.0 LUFS, −1.4 dBTP**.

### F14. Reference sheets: wrong ethnicity and a European "old town" (2026-11-26 ~01:00 EAT)
- **What:** the first 18 reference candidates had South Asian / Middle Eastern faces. "Warm brown skin" wasn't specific enough, so the model fell back on its default. The Harar wall came out as a **crenellated European castle wall with glass windows**, the "generic old town" error the research brief warned about.
- **Fix:** each character description now says "Ethiopian … from Harar, with Habesha features, dark brown skin". The wall description uses the research facts (rubble stone with limewash, flat-roofed two-storey houses, few street-facing windows, wooden doors) and says "no towers, no battlements, no arches".
- **Result:** the second batch reads as Ethiopian, and the Jugol looks plausible (see `outputs/review/refs_sheet.png`: left three columns are the old prompts, right three the new). Written up as EXPERIMENTS E3a.

### F15. Wan 2.2 on a Kaggle T4: CUDA out of memory at the first denoising step (2026-11-26 ~02:45 EAT)
- **What:** the first GPU job (s07, 544×960, 81 frames, 30 steps) got through setup, the ~20 GB weight download, fp32 CPU text encoding (149 s) and model load.
  It then failed in the transformer's FFN: `CUDA out of memory. Tried to allocate 294 MiB … 14.56 GiB total … 13.71 GiB allocated by PyTorch`.
  Peak 15.01 GB. The kernel's `results.json` recorded the error, and `video-fetch` registered 0 clips (it logs a failed result rather than crashing).
- **Why:** a 5B-parameter transformer in fp16 is about 10 GB of weights before any activations, on a 14.6 GB card. Kaggle gave **two** T4s and we used one.
- **Fix (attempt 2):**
  1. `enable_layerwise_casting(storage=float8_e4m3fn, compute=float16)`: weights are stored in fp8 (~5 GB) and each layer is upcast just for its compute.
  2. The VAE moves to the **second T4**, and the latents are decoded there with tiling.
  3. `PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True`.
- **Fallback if it fails again:** fewer frames (49) and 480×832, then Ken Burns for every shot. The film never depends on this stage (ARCHITECTURE.md).
- **Result (attempt 2, 03:05 EAT):** **success.** s07, 544×960, 81 frames, 30 steps: 1036.6 s of GPU time. Peak **7.33 GB** on GPU 0 (fp8-stored transformer) and 5.46 GB on GPU 1 (VAE decode).
  The text encoder took 152 s on the CPU. The clip was checked frame by frame: identity is stable across all 81 frames, with no NaN or black frames from fp16.
