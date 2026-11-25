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
- **Tried:** re-ran with `UV_HTTP_TIMEOUT=600` and fewer concurrent downloads (now the default in `make music-setup`).
- **Result:** *(in progress)*

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
