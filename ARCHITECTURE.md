# ARCHITECTURE

## One contract, eight stages
`storyboard.json` is the only interface between stages. It is validated by Pydantic models
(`pipeline/models.py`), and the committed JSON Schema (`schema/storyboard.schema.json`) is *generated* from those
models. A test fails if the two drift. Every stage validates the storyboard before doing anything.

```
 storyboard.json ──► validate
        │
        ├─► script      Gemini: draft translation of text_en → narration.text (native-speaker reviewed)
        ├─► narration   TTS per shot (Addis AI | Gemini) ─► outputs/narration/<shot>/<key>.wav
        │                 └─► deterministic post-process: atempo + warmth EQ ─► <key>.t0.90_warm.wav (E1b)
        │                 └─► timeline.json  (shot length = max(min_duration, lead + measured voice + tail))
        ├─► subtitles   timeline + text_en ─► outputs/subs/{9x16,16x9}.ass, en.srt
        ├─► refs        character/location sheets (FLUX.2 klein 4B) ─► approve
        │     └─► keyframes   klein 4B + approved refs (≤4, <512²) ─► approve
        │           └─► video   Kaggle GPU, Wan 2.2 TI2V-5B (async submit/fetch) ─► outputs/clips/
        ├─► music       ACE-Step 1.5, local GPU, one candidate per seed ─► choose-music
        └─► assemble    FFmpeg only: segments → dissolves → subtitles → end card; VO + ducked score → loudnorm
                          ─► outputs/final/radio_cut.mp4, a_little_further_{9x16,16x9}.mp4
```

| Stage | Reads | Writes | Cache key = hash of |
|---|---|---|---|
| script | `shots[].narration.text_en` | `outputs/script/translation_<lang>/<key>.json` | all lines, system prompt, language, model |
| narration | `shots[].narration` | `outputs/narration/<shot>/<key>.wav` + `timeline.json` | text, language, voice, speed, style, provider, model |
| subtitles | timeline, `text_en` | `outputs/subs/*` | deterministic, rebuilt every run (cheap) |
| refs | `characters[]`, `locations[]`, `meta.style_block` | `outputs/refs/<id>/<key>.png` | ref prompt + description + style, seed, size, model |
| keyframes | `shots[].keyframe`, approved refs | `outputs/keyframes/<shot>/<key>.png` | full prompt, seed, size, **hashes of the ref images** |
| video | approved keyframe, `shots[].motion` | `outputs/clips/<shot>/<key>.mp4` | **keyframe hash**, motion prompt, seed, size, frames, steps |
| music | `music` | `outputs/music/score/<key>.wav` | caption, lyrics, bpm, key, duration, seed, model |
| assemble | everything approved + timeline | `outputs/final/*` | hashes of every input segment + edit parameters |

Because each key includes the hashes of its upstream assets, a change propagates exactly as far as it should:
- A new narration line regenerates that shot's audio, its subtitles and the edit. Images and clips are untouched.
- A new keyframe prompt regenerates that keyframe, which changes its hash and therefore that shot's clip key. Other shots are untouched.

## The choke point: `call_model()`
`pipeline/core/calls.py`. Stages never talk to providers directly. For each asset they pass the exact inputs it
depends on and a `run(tmp_path)` callback:

1. **Cache:** compute the key and look for `outputs/<stage>/<item>/<key>.<ext>`. If it exists, reuse it. That's the whole cache: no
   database, no manifest. The filesystem is the index and the asset is its own proof of existence.
2. **Dry-run:** with `--dry-run`, record `reuse` / `generate`. For `generate`, diff the inputs against the item's latest
   sidecar and report *which field changed* (`changed: speed`).
3. **Retries:** up to 3 attempts. Exponential backoff (2 s, 4 s, …) or `Retry-After`. Only `ProviderError(retryable=True)` is retried:
   408/409/425/429/5xx and network errors. 4xx client errors fail fast. Missing credentials raise
   `MissingCredentials` and are never retried.
4. **Atomic writes:** the callback writes `<key>.<ext>.part`, which is renamed only on success. A crash never leaves a "cached" half-file.
5. **Logging:** *every attempt*, successful or not, appends one line to `runs.jsonl`: ts, run_id, stage, shot_id,
   provider, model, prompt, params, seed, input_key, attempt, status, latency_s, error, plus provider extras
   (audio_s, est_cost_usd/etb, est_neurons, gpu_s, peak_vram_gb).
6. **Provenance:** next to every asset, `<key>.meta.json` records the inputs, model, run id, latency and licence.
   `python -m pipeline audit` checks every asset has a sidecar and an ok line in runs.jsonl.

GPU jobs on Kaggle can't run inside the call, so `register_external()` brings their outputs into the same cache
with the same log line. The key is computed from the inputs **that were submitted**, which are stored in the job manifest.

## Providers
`pipeline/providers/`: one small file per external service behind typed Protocols (`TTSProvider`,
`ImageProvider`, `TextProvider`, `MusicProvider`). Model ids, voices and list prices live in
`config/providers.toml`. Swapping Addis ↔ Gemini TTS is a storyboard or config change, not a code change.
Request/response quirks stay inside the provider:
- Addis needs a `client_request_id` (we send a deterministic hash, so retries are idempotent).
- klein references must be under 512².
- Gemini TTS returns raw 24 kHz PCM.

## Failure handling and fallbacks
| Failure | Handling |
|---|---|
| 429 / 5xx / timeouts | retried with backoff in `call_model`, every attempt logged |
| Larger text model overloaded (503) | `script` falls back from `gemini-3.8-flash` to `gemini-3.5-flash-lite` (different key, logged) |
| Missing API key | clear message naming the variable. `film` skips that stage and continues with cached assets/fallbacks |
| Refs or keyframes not approved | downstream stages refuse them, except with `--allow-draft` for rough cuts |
| No Wan clip (quota, OOM, queue, fp16 NaNs) | **assembly automatically uses Ken Burns** over the keyframe, so GPU problems never block the film |
| No keyframe yet | labelled placeholder card, so the edit and timing can still be reviewed |
| No chosen score | placeholder drone (the radio cut's temp track) |
| Kaggle kernel timeout | `results.json` is rewritten after every clip, so finished clips survive |

## Why the GPU stage is asynchronous
Wan 2.2 on a free T4 takes minutes per clip and queues unpredictably. `video-submit` bundles approved keyframes
plus motion prompts into a Kaggle dataset and pushes `kaggle/wan_i2v/run.py`. `video-fetch` registers whatever
finished. `make film` never waits on a GPU: it uses the clips that exist.

T4-specific design (`kaggle/wan_i2v/run.py`). These are the lessons of FAILURES F1 and F15:
- The official Wan repo hard-requires FlashAttention 2, which the T4 can't run, so we use Diffusers + PyTorch SDPA.
- The T4 has no bf16, so the transformer runs in fp16.
- The UMT5-XXL text encoder is unstable in fp16, so every prompt is encoded once in fp32 on the CPU and the encoder is freed before the transformer loads (Kaggle has about 29 GB RAM).
- The transformer is stored in **fp8** and computed in fp16 (`enable_layerwise_casting`). The first fp16-only attempt ran out of memory at 15.0 GB on a 14.6 GB T4.
  With fp8 storage the peak is 7.3 GB.
- The VAE decodes on the **second T4** (Kaggle provides 2), with tiling.
- Clips render at **1280×704 (16:9)**, TI2V-5B's native 720p. Assembly upscales them for 16:9 and crops them for 9:16.

## Framing: one 16:9 master, two deliveries (producer decision)
Keyframes are generated at **1920×1088**, the maximum klein output, and Wan clips at 1280×704. The 9:16 film is *cut from* that
master. Each shot has a `keyframe.vertical_center` (0–1) saying where along the width the vertical crop sits, so off-centre subjects
(the grandmother in s05, the tailor in s03) stay in frame. The crop is an **edit** parameter: it is not part of the keyframe cache
key, so re-framing never regenerates an image. When the 16:9 master replaced the earlier square frames, each shot passed its
approved square frame as a **composition reference** (`keyframe.composition_ref`), so the approved look survived the format change.

## Assembly (deterministic, no AI)
`pipeline/stages/assemble.py`:
- **Picture:** each shot becomes a segment, chosen in this order: Wan clip for that ratio (head-trimmed, gently retimed or held), else Ken Burns over the 1024² keyframe, else a placeholder.
  - Ken Burns crops the square to 16:9 or 9:16 first, oversamples 2×, then `zoompan`s, which avoids distortion and reduces jitter.
  - Segments are chained with `xfade` at the timeline's cut points.
  - The ASS subtitles are burned in, and the AI end card (Pillow text, never generated text) closes the film.
- **Sound:**
  - Narration clips are placed with `adelay` at their measured offsets and pre-levelled to −16 LUFS.
  - The score is levelled to −24 LUFS with fades, then ducked under the voice by `sidechaincompress` (threshold 0.02, ratio 6, attack 300 ms, release 1500 ms).
  - The mix gets a **two-pass `loudnorm`** to −14 LUFS / −1 dBTP.
- **Export:** H.264 CRF 18, 24 fps CFR, AAC 192 kbps, `+faststart`, at 1080×1920 and 1920×1080.

Intermediate renders are cached under `outputs/_tmp/` by content hash, so a re-edit only re-renders the changed segments.

## Reproducibility
- `make film` from a clean clone with **no keys** rebuilds both films. Every model output is committed under `outputs/`,
  so every model stage is a cache hit, and assembly is deterministic FFmpeg.
- With keys, only assets whose inputs changed are regenerated. `make dry-run` shows which ones, and why.
- Prompts, seeds and parameters live in `storyboard.json` / `config/providers.toml`, never hidden in code.
- Heavy ML dependencies are isolated: ACE-Step runs in its own uv project (`vendor/`, installed by `make music-setup`),
  and Wan runs only on Kaggle. The main environment is pydantic, requests, pillow and typer.
