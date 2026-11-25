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
- **Listener results:** *pending*
- **Conclusion / change:** *pending*

## E2. Translation model: Gemini 3.8 Flash vs 3.5 Flash-Lite for Amharic narration
- **Hypothesis:** the larger model gives more natural spoken Amharic. Flash-Lite is fine for bulk work but makes errors in a low-resource language.
- **What happened:** 3.8 Flash was unavailable (503 × 4, F9), and the fallback Flash-Lite produced the draft (key in runs.jsonl, stage `script`).
- **Observed errors in the Flash-Lite draft** (agent reading, to be confirmed by a native speaker):
  - s03 "ሰብቺዎች" is not a word for tailors (expected "ልብስ ሰፊዎች").
  - s06 "እናትየዋ" means "the mother", not "my mother" ("እናቴ"), and the clause "አብረዋቸው ይዟት ይዞ ነበር" is ungrammatical.
  - s02 "ከክህሎት ውጪ የያዙት ትንሽ ነገር ነበረ" is awkward.
- **Status:** *in progress.* Re-run with 3.8 Flash when available, then have a native speaker rate both drafts line by line.
- **Change so far:** the draft was **not** applied. Narration stays unapproved until native review (Gate 1).

## Planned
| # | Question | Variable | Evidence |
|---|---|---|---|
| E3 | Do approved reference sheets keep characters consistent? | refs on vs off (`keyframe.use_refs`) | image-embedding cosine similarity vs the approved ref, plus eyeballing |
| E4 | klein-4B vs schnell | model, same prompt and seed | latency, neurons, look |
| E5 | Short vs detailed image prompt | prompt length | prompt adherence notes |
| E6 | Fixed vs varied seed | seed | variation across 4 candidates |
| E7 | Motion-only vs full re-description in the I2V prompt | motion prompt | artefacts in Wan clips |
| E8 | Wan draft resolution and steps on T4 | 544×960 @ 30 steps vs 704×1280 | GPU seconds, peak VRAM, artefacts |
| E9 | Wan clip vs Ken Burns for the same shot | segment kind | viewer preference |
| E10 | ACE-Step candidates | seed (4) under the same caption | listening under the narration at phone volume |
| E11 | Ducking settings | sidechain threshold/ratio | narration intelligibility at low volume |
| E12 | *(ceiling)* Afaan Oromo / Tigrinya narration via Addis | language | native-speaker rating, failure notes |
