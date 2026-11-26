# EXPERIMENTS

Format: hypothesis → independent variable (one change) → controls → procedure → result (with evidence) →
conclusion → what changed. Evidence is the `input_key` of each runs.jsonl line, or listener notes. Nothing here is
estimated or invented. Planned entries are marked *planned* until they are run.

---

## E1. Which Amharic voice should narrate? (Addis AI voices vs Gemini TTS)
- **Hypothesis:** a voice tagged for *narration* (`am-loza`) will be preferred over conversational voices, and a native
  Amharic voice (Addis) will beat a multilingual one (Gemini `Kore`) on pronunciation.
- **Independent variable:** voice. **Controls:** the same Amharic line (s01), speed 1.0, no style prompt, normalised to
  48 kHz mono with silence trimmed (`media.to_wav`).
- **Procedure:** `python -m pipeline audition --text "<s01 line>"` renders each voice and copies them to
  `outputs/audition/blind/voice_A…E.wav`. The key is kept apart (`KEY_do_not_share.txt`). Listeners hear A–D without names
  and pick a favourite, plus the "clearest pronunciation".
- **Measured so far:**

| Label | Voice | Latency (s) | Audio (s) | runs.jsonl key |
|---|---|---|---|---|
| A | addis `am-loza` (female, "smooth studio narration") | 74.3 | 5.12 | 21d47e3d457b3bf5 |
| B | addis `am-sara` (female, "motherly warm inspiring") | 74.8 | 5.29 | 16047ed55216e261 |
| C | addis `am-hamen` (female, "warm conversational", default) | 159.1 | 5.71 | b175ed7e4ba57825 |
| D | addis `am-melat` (female, "authentic conversational") | 103.4 | 5.17 | 32223fcd01d4e706 |
| E | gemini `Kore` (female) | n/a | n/a | 503 × 3 (F9); not included in the blind test |

- **Side finding:** Addis took **74–159 s to synthesise ~5 s of audio**, roughly 15–30× slower than real time. For 11 lines that is about 15–20 min,
  so narration runs as a background job, and caching it matters more than expected.
- **Listener results (2026-11-25, blind A–D):** the producer and her testers independently chose **B** (`am-sara`).
  Their note: *"a little fast, and it needs more warmth."* (Their names and exact number go in DESIGN.md test notes.)
- **Conclusion:** the hypothesis was **wrong**. Listeners preferred the voice tagged "motherly, warm, inspiring" over the one tagged
  "studio narration". For a family tribute, warmth beat polish.
- **Change:** `narration.voice = am-sara` on every shot, and it is the default in `config/providers.toml`. That led to E1b.

## E1b. Can we slow the voice down with the provider's `speed` parameter?
- **Hypothesis:** Addis' `speed` < 1 lengthens the same line proportionally.
- **Variable:** speed ∈ {1.0, 0.85, 0.9}. **Controls:** same voice (`am-sara`) and same s01 line.
- **Result (runs.jsonl):**

| speed | audio length (s) | expected at 1.0 = 5.29 s | latency (s) |
|---|---|---|---|
| 1.0 | 5.29 | n/a | 74.8 |
| 0.85 | **5.30** | 6.22 | 49.5 |
| 0.90 | 5.84 | 5.88 | 69.0 |

- **Conclusion:** `speed` is **not reliably honoured**. 0.85 gave the same length as 1.0. 0.9 came out longer, but by an amount consistent with
  take-to-take variation (TTS is stochastic). We can't depend on it.
- **Change:** tempo and warmth moved into a **deterministic post-process** in the narration stage:
  - `atempo=0.9` (pitch-preserving), plus a gentle low-shelf +2.5 dB @160 Hz, high-shelf −2.5 dB @7.5 kHz and light 2:1 compression.
  - The settings are `meta.vo_tempo = 0.9` and `meta.vo_warmth = true` in the storyboard.
  - Derived files are keyed by the raw take plus the settings, so tuning them never re-bills TTS.

## E2. Translation model: Gemini 3.8 Flash vs 3.5 Flash-Lite for Amharic narration
- **Hypothesis:** the larger model gives more natural spoken Amharic. Flash-Lite is fine for bulk work but makes errors in a low-resource language.
- **What happened:** 3.8 Flash was unavailable (503 × 4, F9), and the fallback Flash-Lite produced the draft (key in runs.jsonl, stage `script`).
- **Observed errors in the Flash-Lite draft** (agent reading, to be confirmed by a native speaker):
  - s03 "ሰብቺዎች" is not a word for tailors (expected "ልብስ ሰፊዎች").
  - s06 "እናትየዋ" means "the mother", not "my mother" ("እናቴ"), and the clause "አብረዋቸው ይዟት ይዞ ነበር" is ungrammatical.
  - s02 "ከክህሎት ውጪ የያዙት ትንሽ ነገር ነበረ" is awkward.
- **Re-run (2026-11-25 ~23:50 EAT), same prompt + a 3-term glossary:**
  - `gemini-3.8-flash` succeeded on its 3rd attempt (two earlier tries: a 180 s read timeout, then a 503). Latency 164.9 s.
  - `gemini-3.6-flash` failed 6/6 with 503 "high demand". There is no draft from it to compare.
- **3.8 Flash vs 3.5 Flash-Lite (agent reading; producer to confirm):**
  - 3.8 used the correct terms: ልብስ ሰፊዎች (tailors), እናቴ (my mother), በማዕረግ ተመረቅሁ (graduated with honours).
  - Its sentences are natural and spoken ("ማታ ማታ ቢደክማትም እንኳ፣ ታጠና ነበር።").
  - One oddity remained, s03 "እያያዙ", which the agent removed.
  - **Caveat:** the glossary was added for the 3.8 run, so this isn't a single-variable comparison. Part of the improvement is the glossary.
- **Conclusion:** for a low-resource language, the larger model is worth the 503 retries. The fallback model is only safe with a glossary and native review.
- **Change:** the 3.8 draft (+ s03 edit) went into `narration.text`, pending the producer's line-by-line approval (Gate 1).

## E3a. Does naming the ethnicity explicitly change who the model draws?
- **Hypothesis:** "warm brown skin" is too vague. The model will default to non-Ethiopian faces unless the ethnicity and region are named.
- **Variable:** the character description text (vague vs "Ethiopian from Harar, Habesha features, dark brown skin"). The same goes for the wall description (generic vs research-grounded).
- **Controls:** the same model (klein-4B), the **same seeds** (101–104, 202–204, 301–303, 501–503, 701–703), the same style block and size.
- **Result:** 18 candidates before, 18 after (runs.jsonl, stage `refs`; side by side in `outputs/review/refs_sheet.png`).
  - Before, every face read as South Asian / Middle Eastern.
  - After, all 15 character images read as Ethiopian.
  - Before, the walls were a crenellated European castle or Mediterranean houses with glass windows. After, they show rubble-stone, flat-roofed houses on a dirt alley.
- **Conclusion:** the model's default identity is not ours. Specificity grounded in the research brief fixed both problems at no extra cost.
- **Change:** the descriptions are updated in `storyboard.json`. Since every keyframe prompt reuses them verbatim, the fix propagates to all shots.

## E3b. Conditioning on the whole reference sheet vs the portrait panel only
- **Observation that triggered it:** with full two-panel character sheets (full body | head-and-shoulders) as klein `input_image`s, 4 of 22 keyframes
  copied the **two-panel layout** into the scene. The same person appeared twice side by side: s03 (both), s05 (seed 1006), s06 (1006) and s08 (1009).
  The s03 "close-up of hands" became two portraits.
- **Change (one variable per shot group):**
  1. Characters are conditioned on the right-hand **portrait crop** only (derived file `<key>.portrait.png`).
  2. Shots with people get the prefix "a single cinematic film frame of one moment, not a reference sheet".
  3. Hands-only inserts (s03, s05) use **no** face references (`keyframe.use_refs: false`).
- **Controls:** same seeds (1002–1012), same prompts, same model and size. s01 has no people, so its prompt was left unchanged and it was reused from cache.
- **Result:** 20/20 new candidates are single scenes. **0 duplicated people** (was 4/22). Faces stay recognisably the approved references
  (side by side in `outputs/review/keyframes_sheet.png`). Side effect: without face refs, s03 still drew the tailor (a medium shot rather than hands only),
  which the director accepted. s11 lost "from behind" and is being regenerated with stronger wording.
- **Conclusion:** reference images are copied *as compositions*, not only as identities. Crop references to exactly what should transfer.

## E4. Can Wan 2.2 TI2V-5B run on a free Kaggle T4? fp16 weights vs fp8-stored weights
- **Hypothesis:** the 5B transformer in fp16 (~10 GB) plus activations will not fit on a 14.6 GB T4. Storing the weights in fp8 and computing
  in fp16 (Diffusers `enable_layerwise_casting`) will fit, without visible quality loss.
- **Variable:** transformer weight storage dtype. **Controls:** the same shot (s07), keyframe, prompt, seed 7, 544×960, 81 frames,
  30 steps, guidance 5.0, the same Kaggle "T4 x2" machine, and the text encoder fp32 on CPU in both runs.
- **Result (runs.jsonl stage `clips`; kernel results.json):**

| Run | Storage | VAE on | Outcome | GPU time | Peak VRAM GPU0 / GPU1 |
|---|---|---|---|---|---|
| 1 | fp16 | GPU 0 | `CUDA out of memory` at the first denoising step | 6.3 s (after setup) | 15.01 GB / n/a |
| 2 | fp8 storage, fp16 compute | GPU 1 | **ok**, 81 frames | 1036.6 s | 7.33 GB / 5.46 GB |

- **Quality check:** frames 0/40/80 were inspected. Identity is stable, the headscarf and lighting stay consistent, and there are no NaN or black frames.
- **Conclusion:** fp8 *storage* halves the weight memory, and the free T4 becomes usable. Splitting the VAE onto the second GPU
  uses hardware we were already given. It costs about 17 GPU-min per 3.4 s clip at this size.
- **Change:** both settings are now in `kaggle/wan_i2v/run.py`. With 7 GB of headroom, the batch was moved to the native 1280×704.

## E5. Does an approved frame survive a format change if it's passed as a composition reference?
- **Context:** the producer moved the master format from 1024² to 16:9 (1920×1088) *after* approving the square keyframes. Regenerating
  from text alone would throw those approvals away.
- **Variable:** a `keyframe.composition_ref` pointing at the approved square frame, passed as the first klein input image.
  **Controls:** the same seed, prompt, character refs and model.
- **Result:** 10/10 regenerated 16:9 frames kept the approved composition, palette, wardrobe and pose: the gate, the couple
  walking, the tailor at the machine, the stall, the lamp, the graduation, the office and the desk (`outputs/review/keyframes_sheet.png`). The format
  change cost one image per shot (3.9k neurons) and no re-approval round. s11 was regenerated fresh (its square version was rejected).
- **Conclusion:** a reference image carries *composition* as strongly as identity. E3b showed the harmful side of the same effect.

## E12 (ceiling). Can the same narration be made in Afaan Oromo, Tigrinya and Harari, the languages of Harar's region?
- **Why these languages:** Harar is the Harari people's city, inside an Oromo-majority region; Tigrinya is a control language with good provider support.
- **Procedure:** `pipeline/tools/languages.py` translates s01 + s11 with Gemini (same prompt as E2), then synthesises with a female voice:
  Addis `om-obse` (Oromo, "Narration"), Addis `ti-saba` (Tigrinya, "Storytelling"), and for Harari, which **no provider lists**,
  Gemini TTS `Kore`. Outputs are in `outputs/ceiling/`, all calls are in runs.jsonl (stages `script`, `ceiling`), and the summary is in `outputs/ceiling/results.json`.
- **Measured:**

| Lang | Translation model (attempts) | TTS | ok? | Audio s01 / s11 (s) | TTS latency (s) |
|---|---|---|---|---|---|
| om | 3.8 Flash 503 → **3.5 Flash-Lite** (2) | Addis `om-obse` | yes | 4.6 / 7.5 | 8.8 / 9.2 |
| ti | **3.8 Flash** (3: timeout, 503, ok) | Addis `ti-saba` | yes | 5.4 / 7.2 | 11.1 / 11.6 |
| hrr | **3.8 Flash** (3: 503, 503, ok) | Gemini `Kore` | "yes" | 5.8 / 8.4 | 7.5 / 5.1 |

- **What the outputs show (agent reading; native speakers needed for real ratings):**
  - **Tigrinya** reads as plausible Tigrinya (e.g. "ጥንታዊ መናድቕ ሓረር" for "Harar's ancient walls").
  - **Oromo** came from the weaker fallback model. One phrase looks off ("dallaa Harar baraa"), so it needs a native check.
  - **Harari is the important finding:** every API call *succeeded*, but the text is mostly **Amharic** with a few Harari- or
    Arabic-looking words (ቦኡ, ጁገልቤ, ቆዲም). The voice is a multilingual model reading Ge'ez script, so it is almost certainly
    Amharic pronunciation. **A 200 OK is not evidence of language support.** For a low-resource language without provider support, the
    pipeline can produce something that *looks* right to a non-speaker and is wrong.
- **Conclusion:** Oromo and Tigrinya narration are feasible today with Addis, pending native rating. Harari is not: it would need a
  native translator and either a native voice actor (with consent) or a fine-tuned voice. The film stays in Amharic.
- **Change:** none to the film. The language list in `script.LANG_NAMES` and the probe tool remain, so a native-reviewed Oromo or
  Tigrinya version is one `translate --language om --apply` plus `narration` away.

## E7. Motion-prompt wording: "the camera …" vs camera-free phrasing (image-to-video)
- **Hypothesis (from the brief's tip):** an I2V prompt should describe motion and camera only. We added: *the word "camera" itself is
  ambiguous to a video model when a person is in frame.*
- **Evidence:** in the batch of 6 Wan clips (same model and settings), 2 prompts used "the camera …":
  - s07 ("The camera is fixed"): clean.
  - s11 ("The camera rises slowly behind her"): **failed**. The subject picked up a camera mid-shot (FAILURES F17).
  - The 4 prompts that described camera motion as *push in / follows gently* had no props appear.
- **Change:** s11 rephrased as "slow upward crane movement from behind her … she stands still with both hands on the railing". Re-run with the same seed and keyframe:
  no prop, subject still, gentle rise. Both runs are in runs.jsonl (stage `clips`, item s11).
- **Conclusion:** describe camera moves with film terms (crane, push-in, dolly) and *pin the subject's hands and pose* when a person is in frame.
  n = 1 failure, so this is a strong anecdote, not a statistic.

## E8. Wan resolution on a T4: 544×960 vs 1280×704
| Run | Resolution | Frames / steps | GPU time per clip | Peak VRAM GPU0 / GPU1 |
|---|---|---|---|---|
| E4 run 2 (s07) | 544×960 (522k px) | 81 / 30 | 1036.6 s | 7.33 / 5.46 GB |
| overnight batch, 6 clips | 1280×704 (901k px) | 81 / 30 | 2193.6–2205.2 s (mean ≈ 2199 s) | 8.94 / 6.93 GB |
| s11 re-run | 1280×704 | 81 / 30 | 2456.3 s | n/a |
- **Result:** 1.73× the pixels cost **2.1×** the GPU time (attention is super-linear in tokens), and only +1.6 GB VRAM thanks to fp8 storage.
- **Conclusion and change:** native 720p fits comfortably and was worth it, because the 9:16 film crops from this master (a 396 px wide crop instead of 306 px).
  7 clips × ~37 min ≈ 4.3 GPU-hours of the ~30 h weekly Kaggle quota.

## E10. Choosing the score: 4 ACE-Step candidates, same caption, different seeds
- **Hypothesis:** with a fixed caption (tizita mood, krar/masinqo/washint, "builds to a hopeful final section"), seeds will differ mostly in arc and density.
  The best bed for narration is the one with the least energy in the speech band and a real build at the end.
- **Controls:** the same caption, lyrics `[Instrumental]`, 72 bpm, A minor, 95 s, turbo DiT + 0.6B LM, local RTX 3070 with CPU offload. **Variable:** seed ∈ {11, 22, 33, 44}.
- **Measured (ffmpeg ebur128 / volumedetect on each candidate):**

| Seed | Integrated loudness (LUFS) | 1–4 kHz band vs full (dB) | Last quarter vs first two thirds (dB) | Generation time (s) |
|---|---|---|---|---|
| 11 | −15.7 | −12.5 | −3.7 | 31.5 |
| 22 | −14.9 | −10.4 | −4.0 | 32.4 |
| **33** | −16.0 | −12.5 | **+4.8** | 33.6 |
| 44 | −16.5 | −8.8 | −2.8 | 41.2 |

- **Decision (director, provisional):** seed **33**. It is the only one that actually builds toward the end, and it ties for the least speech-band energy.
  The score is **end-aligned** (`music.align = "end"`): the first 9.5 s of the 95 s track are skipped, so the build lands on s10–s11 and the music ends with the film.
- **Listening test:** blind kit in `outputs/review/music_blind/score_A–D.m4a` (full narration mix; key kept separately). *Pending: producer/testers by ear.*
  If they pick another, it's `python -m pipeline choose-music <seed> --why …` plus `assemble`, with no model calls.

## E11. Ducking depth: how far should the score drop under the voice?
- **Procedure:** render the *ducked music stem alone* (same voice sidechain, chosen score, end-aligned), then measure mean level inside the narration windows vs in the gaps between lines.
- **Measured:**

| Setting (sidechaincompress) | Music under speech | Music in gaps | Reduction under speech vs no ducking |
|---|---|---|---|
| none | −26.0 dB | −26.9 dB | n/a |
| gentle: threshold 0.05, ratio 3 | −33.2 dB | −27.7 dB | 7.2 dB |
| brief's starting point: threshold 0.02, ratio 6 | −41.5 dB | −32.2 dB | 15.5 dB |

- **Reading:** the voice is pre-levelled 8 LU above the music (−16 vs −24 LUFS). The brief's starting point puts the score about 23 dB under the voice and doesn't let it
  recover in the pauses (gaps −32 dB vs −27 dB). For a tribute, the music should be felt.
- **Decision:** the gentle setting. That's about 15–17 dB of voice-over-music separation during speech, and the score lifts back in the pauses. To be confirmed on a phone speaker in user test 2.

## E13 (ceiling: a tool for families). Can a relative's plain-text story become a runnable storyboard?
- **Tool:** `python -m pipeline draft-storyboard story.txt --language am --title …` (`pipeline/tools/draft_storyboard.py`). Gemini gets the real JSON Schema
  and drafting rules (no names, every family detail flagged `pending-family`, motion prompts without the word "camera" per E7, and an AI end card). The
  output is validated by the pipeline's own Pydantic models, and errors are fed back for up to 2 repair rounds.
- **Test input:** a generic, invented 3-paragraph story (`docs/examples/radio_repairer_story.txt`, the assignment's "father who repaired radios" example).
  It is not the producer's family, so no private details went to the free tier.
- **Measured (runs.jsonl stage `draft`):**
  - **22 calls → 1 success.** 18 failures were 503 "high demand" and 3 were network errors, across 7 attempts about 5 min apart. The success came from the fallback **Flash-Lite** in 12.9 s.
  - The draft was **valid on round 0**: 9 shots, 1 character, **9/9 fact flags `pending-family`**, Amharic narration plus English subtitles.
- **What validation could *not* catch:** the draft's end card says **"In memory of our father"**. The story never says the father died.
  The schema guarantees shape, not truth. Exactly as with the main film (the `fact_flags` protocol and the heritage-ethics reviewer agent), a human or reviewer pass
  over every claim is required before anything is generated.
- **Conclusion:** the "storyboard as contract" design makes a family tool cheap: one prompt plus the existing validator. Its weakest link is the free LLM's
  availability (1 in 22 calls succeeded on the deadline day), and its riskiest is plausible invented facts. Next step: run the reviewer agent automatically and
  make the end card a template rather than model text.

## Planned
| # | Question | Variable | Evidence |
|---|---|---|---|
| E6 | Fixed vs varied seed | seed | variation across 4 candidates |
| E9 | Wan clip vs Ken Burns for the same shot | segment kind | viewer preference |
