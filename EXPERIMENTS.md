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
| E | gemini `Kore` (female) | n/a | n/a | 503 × 3 (F9), retry pending |

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

## Planned
| # | Question | Variable | Evidence |
|---|---|---|---|
| E3 | Do approved reference sheets keep characters consistent? | refs on vs off (`keyframe.use_refs`) | image-embedding cosine similarity vs the approved ref, plus eyeballing |
| E5 | Short vs detailed image prompt | prompt length | prompt adherence notes |
| E6 | Fixed vs varied seed | seed | variation across 4 candidates |
| E7 | Motion-only vs full re-description in the I2V prompt | motion prompt | artefacts in Wan clips |
| E8 | Wan resolution on T4 | 544×960 (E4 run 2) vs 1280×704 (overnight batch) | GPU seconds per clip, peak VRAM |
| E9 | Wan clip vs Ken Burns for the same shot | segment kind | viewer preference |
| E10 | ACE-Step candidates | seed (4) under the same caption | listening under the narration at phone volume |
| E11 | Ducking settings | sidechain threshold/ratio | narration intelligibility at low volume |
| E12 | *(ceiling)* Afaan Oromo / Tigrinya narration via Addis | language | native-speaker rating, failure notes |
