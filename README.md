# A Little Further: a heritage short, made by a pipeline

*Four generations in Harar, from immigrant tailors to an AI engineer, each giving up something so the next could go a little further.*
A 60–90 s film narrated in Amharic with English subtitles and an original score, built entirely by code from one file: [`storyboard.json`](storyboard.json).

| | |
|---|---|
| Film | `outputs/final/a_little_further_9x16.mp4` (vertical) · `outputs/final/a_little_further_16x9.mp4` (horizontal) |
| First audience prototype | `make radio` → `outputs/final/radio_cut.mp4` (narration + temp music on black) |
| How it was designed and tested | [DESIGN.md](DESIGN.md) |
| How it works | [ARCHITECTURE.md](ARCHITECTURE.md) |
| What I measured / what broke / what it cost | [EXPERIMENTS.md](EXPERIMENTS.md) · [FAILURES.md](FAILURES.md) · [COSTS.md](COSTS.md) |
| Consent, privacy, licences | [ETHICS.md](ETHICS.md) |

## Showcase site
`site/` is an interactive page (inspired by *The Window*). It has the film in both formats plus the radio cut; every shot with its prompts, seed,
9:16 crop and fact flags; the pipeline with a run-log chart computed from `runs.jsonl`; what we learned; and the audience tests.
`make site` rebuilds its data and web media from the pipeline's own records. Serve it statically: `python -m http.server -d site`, Vercel or GitHub Pages.

## One command
```bash
git clone <this repo> && cd <repo>
make film          # = uv sync + python -m pipeline film
```
**No API keys are needed to reproduce the film.** Every model output the film uses is committed under `outputs/` with a sidecar
`.meta.json` (narration takes, reference sheets, keyframes, Wan clips and the chosen ACE-Step score), so every model stage is a cache hit and
assembly is deterministic FFmpeg. You need **uv** and **FFmpeg ≥ 6**. The rendered MP4s are not committed; `make film` rebuilds them
(about 6 minutes on a laptop CPU) and prints how many model assets were reused vs generated. Only the chosen score candidate is committed:
regenerating the other three needs ACE-Step (`make music-setup`). If no chosen score is cached, the edit falls back to a synthetic temp drone and says so.

With keys (`cp .env.example .env`), the same command regenerates **only** what changed in the storyboard:
```bash
make dry-run       # what would be generated vs reused, and which field changed
make film
```

## What happens
```
storyboard.json → validate → narration (Addis AI TTS) → subtitles → refs → keyframes (FLUX.2 klein 4B)
                → video (Wan 2.2 on Kaggle, async; Ken Burns fallback) → music (ACE-Step 1.5) → assemble (FFmpeg)
```
Every model call goes through one function that caches by a hash of its inputs, retries transient errors, and appends a
line to [`runs.jsonl`](runs.jsonl) (model, prompt, params, seed, latency, cost estimate, status, attempt).

| Stage | Command | Model / tool | Runs on |
|---|---|---|---|
| translation draft | `python -m pipeline translate` | Gemini 3.8 Flash (fallback 3.5 Flash-Lite) | API, free tier |
| narration | `python -m pipeline narration` | Addis AI TTS, voice `am-sara` (+ deterministic tempo and warmth) | API |
| subtitles | `python -m pipeline subtitles` | none (ASS/SRT) | local |
| reference sheets | `python -m pipeline refs --candidates 3` | FLUX.2 klein 4B | Cloudflare Workers AI |
| keyframes | `python -m pipeline keyframes --candidates 2` | FLUX.2 klein 4B + approved refs | Cloudflare Workers AI |
| moving shots | `make clips` / `make clips-fetch` | Wan 2.2 TI2V-5B (Diffusers, fp16) | Kaggle GPU |
| score | `make music` | ACE-Step 1.5 turbo + 0.6B LM | local RTX 3070 (8 GB) |
| edit | `python -m pipeline assemble` | FFmpeg: Ken Burns, xfade, sidechain ducking, 2-pass loudnorm | local |

Creative gates are data: `python -m pipeline approve refs <id>` / `approve keyframes <shot>` writes the asset's cache key
into the storyboard, and downstream stages only use approved assets.

## Setup with keys
```bash
cp .env.example .env     # GEMINI_API_KEY, ADDIS_API_KEY, CF_ACCOUNT_ID, CF_API_TOKEN, KAGGLE_USERNAME, KAGGLE_API_TOKEN
make setup && make smoke # one tiny call per provider, logged with latency
make music-setup         # ACE-Step 1.5 in its own environment (large download)
```

## Cost
Everything ran on free tiers. Addis AI TTS used the new-account starter credit (5 ETB per generated minute; well under
10 ETB for the whole film). Measured latency, GPU minutes and list-price equivalents per stage are in [COSTS.md](COSTS.md),
generated from runs.jsonl with `make costs`.

## Repository map
```
storyboard.json            the contract (validated by pipeline/models.py; schema/ is generated from it)
pipeline/core/             cache, call_model (retries + logging), runlog, media helpers
pipeline/providers/        addis, gemini, cloudflare (one small file per service)
pipeline/stages/           script, narration, subtitles, refs, keyframes, video, music, assemble
kaggle/wan_i2v/            the Kaggle GPU job for Wan 2.2
music/acestep_job.py       runs inside the ACE-Step environment
outputs/                   every generated asset + .meta.json sidecars; outputs/final = the films
docs/research/             Harar visual research brief (sources, confidence, avoid list)
tests/                     schema, cache isolation, retries/logging, subtitles
```

Made with AI. The characters are fictional, painterly AI actors standing in for real family members, with their
family's consent ([ETHICS.md](ETHICS.md)).
