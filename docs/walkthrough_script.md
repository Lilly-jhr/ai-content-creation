# Walkthrough script (≤ 5 min)

Screen: VS Code with the repo open plus a terminal. Speak in your own words; the bullets are cues, not lines.

## 0:00–0:30 · What this is
- Play the first 10 s of `outputs/final/a_little_further_9x16.mp4`.
- "A 85-second heritage short in Amharic: four generations, from immigrant tailors in Harar to me, an AI engineer.
  Nothing was edited by hand. One file, `storyboard.json`, drives a pipeline that makes every frame and sound."

## 0:30–1:45 · Architecture
- Open `storyboard.json` and show one shot: purpose, keyframe prompt and seed, motion prompt, narration (Amharic + English), and `fact_flags`.
- "This is the contract. It's validated by Pydantic models before every stage, and the JSON Schema is generated from them."
- Show the diagram in `ARCHITECTURE.md`: narration → subtitles → reference sheets → keyframes → Wan on Kaggle → ACE-Step → FFmpeg.
- Open `pipeline/core/calls.py` → `call_model()`: "Every model call goes through one function. It hashes the exact inputs into a cache
  key, retries transient errors, and writes one line to `runs.jsonl`."
- `tail -3 runs.jsonl | jq .`: show model, seed, latency, status.

## 1:45–2:45 · One hard decision (pick one)
**Option A: running Wan 2.2 on a free T4.** The first job ran out of memory at 15 GB on a 14.6 GB card. Show the `results.json` error in
FAILURES F15. The fix: store the weights in fp8, compute in fp16, and decode the video on Kaggle's second GPU, which reached a 7.3 GB peak.
Then I made the film independent of it: if a clip is missing, assembly falls back to a Ken Burns move automatically.

**Option B: the story revert.** I added detailed family facts, then decided the first, simpler story was better. Because the cache
is keyed by content, going back cost exactly one TTS call. Show `git log` and the dry-run.

## 2:45–4:30 · Live: change one line, only that shot regenerates
```bash
# 1. edit one narration line (e.g. s08 "And one day, she graduated." -> a new wording) in storyboard.json
#    (text_en and the Amharic text, or only the Amharic text)
make dry-run          # shows: GENERATE narration s08 (changed: text); every image, clip and other line: REUSE
wc -l runs.jsonl      # note the count
uv run python -m pipeline narration      # one Addis TTS call (pause the recording while it runs)
wc -l runs.jsonl      # +1 (or +n if it retried; show the attempt numbers)
tail -1 runs.jsonl | jq '{stage, shot_id, model, status, latency_s}'
uv run python -m pipeline assemble       # deterministic FFmpeg; no model calls
```
- Say why: "the key for s08's narration changed because its text changed; nothing else's inputs did."
- Optional: show the sidecar `outputs/narration/s08/<key>.meta.json`.

## 4:30–5:00 · Close
- "What I learned: a successful API call isn't proof, so measure the output. Addis ignored its speed setting, and 'Harari' TTS
  came back as Amharic. The film is the part my family sees; the logs are the part that made it possible."
