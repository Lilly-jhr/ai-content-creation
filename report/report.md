---
title: "A Little Further: report"
subtitle: "B2W0 AI-Content Generation: codebase and report"
---

> **DRAFT** prepared with my coding agent from the repository's logs. I will rewrite it in my own words before submitting.
> Every claim points to evidence in the repo: `runs.jsonl`, DESIGN.md, EXPERIMENTS.md (E#), FAILURES.md (F#).

## 1. What I set out to make, and for whom
*A Little Further* is an 85-second film, narrated in Amharic with English subtitles, about four generations of my family:
- great-grandparents who arrived in Harar as strangers and worked as tailors,
- a grandmother with a street-side stall,
- my mother, who worked in the market while studying, graduated, and then worked long office hours so I could learn,
- and me, a software-engineering graduate with honours, on a master's scholarship, working as an AI engineer.

**Audience:** my family and relatives in Ethiopia and the diaspora, watching on a phone in WhatsApp/Telegram, often with the sound low.
**Intent:** that one person's achievement is the accumulated sacrifice of many, and that the story isn't finished.
I wrote this down (DESIGN.md) before any image was generated.

The pipeline:
- One `storyboard.json` (validated by Pydantic models; the JSON Schema is generated from them) drives eight stages.
- Every model call goes through one function that caches by a hash of its inputs, retries transient errors and logs to `runs.jsonl`.
- `make film` rebuilds the film from a clean clone with no API keys, because every model output is committed with its provenance sidecar.

## 2. What I learned from my audience
- **Voice test (test 0):** my sisters and friends heard the opening line in four female voices, blind. They chose B and said it was *"a little fast and needs more warmth"*.
  That led to E1b: the provider ignored its own speed setting, so tempo and warmth became a deterministic step in our pipeline.
- **Radio cut (test 1):** *(to fill in: quotes from ≥3 people, what changed, and the commit that changed `storyboard.json`)*
- **Near-final cut (test 2):** *(to fill in)*
- **A change of mind that wasn't from a tester but was audience-driven:** I added detailed family facts (a named street, decades, a government office),
  then chose to return to the first, simpler story. It's more universal for the family audience, and closer to how we tell it at home.
  Because the cache is content-addressed, the revert cost one TTS call (DESIGN.md "Story revisions").

## 3. The hardest problem and how I solved it
**Making the free GPU produce video at all, without letting it hold the film hostage.**
- The official Wan 2.2 code needs FlashAttention 2, which Kaggle's T4 can't run (F1), so I used the Diffusers pipeline.
- The first job then ran out of memory at 15.0 GB on a 14.6 GB card (F15).
- I stored the 5B transformer's weights in fp8 (computing in fp16), moved the video decoder to Kaggle's second GPU, and encoded prompts once in fp32 on the CPU.
  Peak memory fell to 7.3 GB, which let me render all six motion shots at native 720p (E4, E8: about 37 GPU-minutes per clip).
- I designed the stage so the film never waits for it: GPU jobs are submitted and fetched asynchronously, and any missing clip becomes a Ken Burns
  move automatically. When a clip came back wrong (the narrator suddenly lifted a camera because my prompt said "the camera rises", F17/E7),
  rewording the prompt changed its cache key. The film fell back to Ken Burns for that one shot until the new clip arrived.
- Wan clips are 3.4 s but my shots are 6–11 s. Motion-compensated slow motion plus a hold that continues from the last frame made them fit without a frozen frame (F16).

## 4. Suggested practices, tested honestly
**One that beat my instinct: the radio cut first, with narration setting the shot lengths.**
My instinct was to make pictures first. Timing the narration first gave real numbers. The estimate was 96.6 s; the measured Amharic narration
gave 85.5 s, so the plan already fitted 60–90 s before a single image existed. It also exposed the voice problems (speed, warmth) cheaply, and each shot's
duration is now *derived* from its measured line (`timeline.json`).

**One that didn't work as suggested: "generate a character sheet, then condition every keyframe on it."**
The idea was right, but used literally it backfired. The model copied the sheet's *layout*: 4 of 22 keyframes showed the same person twice, side by side (E3b).
It also didn't fix identity on its own: the first sheets had non-Ethiopian faces and a European castle for Harar, because "warm brown skin" wasn't
specific enough (E3a). What worked was cropping the reference to exactly what should transfer (the portrait), naming the ethnicity and region explicitly,
and grounding place descriptions in research and in my own reference photos.

## 5. Beyond the floor
- **Other languages (E12):** I narrated the opening and closing lines in Afaan Oromo and Tigrinya (Addis AI) and tried Harari, the language of the city in the
  film. Every API call succeeded, but the "Harari" came back as mostly Amharic: no provider supports it. **A 200 OK is not language support.**
  Oromo and Tigrinya are feasible pending native review; Harari would need a native translator and voice.
- **A tool for families (E13):** `draft-storyboard` turns a relative's plain-text story into a schema-valid storyboard. On a test story, the draft was valid first time,
  but it **invented "In memory of our father"** on the end card. Schema validation guarantees shape, not truth, so a fact check stays mandatory.
- **Measured consistency and framing tools:** per-shot vertical crop centres on a 16:9 master; composition references, which let an approved look survive a format change (E5).
- **Observability:** `make costs` generates COSTS.md from runs.jsonl; `make audit` checks every asset has a sidecar and a log line.

## 6. What I would build next
- A small web form where a relative tells a story in Amharic and gets a storyboard draft back. The pipeline already takes everything from one JSON file.
- An identity-consistency metric (face-embedding similarity to the approved reference) to replace eyeballing in E3.
- Native-speaker review loops for Oromo and Tigrinya, and a consented voice for Harari.
