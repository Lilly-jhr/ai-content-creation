# A Little Further

**Report · B2W0 AI-Content Generation: Codebase and Report**
Repository: github.com/Lilly-jhr/ai-content-creation · Evidence references: DESIGN.md, EXPERIMENTS.md (E#), FAILURES.md (F#), runs.jsonl

## 1. What I set out to make, and for whom

*A Little Further* (ጥቂት ወደፊት) is an 85-second film, narrated in Amharic with English subtitles, about four generations of my family:

- great-grandparents who arrived in Harar as strangers and worked as tailors,
- a grandmother with a small stall by the street,
- my mother, who worked in the market while studying, graduated, and then worked long office hours so I could learn,
- and me, a software-engineering graduate with honours, on a master's scholarship, working as an AI engineer.

**Audience:** my family and relatives in Ethiopia and abroad, watching on a phone in WhatsApp or Telegram, often with the sound low.
**Intent:** that one person's achievement is the accumulated sacrifice of many, and that the story is not finished. I wrote both down in DESIGN.md before any image was generated.

The film is the output of a pipeline:

- One `storyboard.json` drives eight stages: translation draft, narration, subtitles, reference sheets, keyframes, video, music and assembly. It is validated by Pydantic models, and the JSON Schema is generated from them.
- Every model call goes through one function that caches by a hash of its exact inputs, retries temporary errors and writes a line to `runs.jsonl`. That log holds 227 calls, failures included.
- `make film` rebuilds both versions from a clean clone with no API keys. An independent audit confirmed this: exit 0, both films at 85.45 s and −14.0 LUFS, every asset with a provenance sidecar (F20).

Changing one narration line regenerates exactly that line; `--dry-run` names the field that changed.

| | |
|---|---|
| Narration | Addis AI, voice `am-sara` (chosen blind by my family), slowed and warmed by our own code |
| Pictures | FLUX.2 klein 4B on Cloudflare Workers AI: reference sheets, then a 1920×1088 master per shot |
| Motion | Wan 2.2 TI2V-5B on a free Kaggle T4 for 6 of 11 shots; Ken Burns moves for the rest |
| Score | ACE-Step 1.5 on my laptop GPU: four candidates, one chosen |
| Edit | FFmpeg only: dissolves, sidechain ducking, two-pass loudness to −14 LUFS, both aspect ratios |

## 2. What I learned from my audience

**Test 0, the voice.** My sisters and friends heard the opening line in four female Amharic voices, blind. They chose B and said it was *"a little fast, and it needs more warmth."* When I tried to slow it, I found the provider silently ignores its own speed setting: speed 0.85 gave 5.30 s, against 5.29 s at 1.0 (E1b). Tempo and warmth became a deterministic step in our own pipeline, so they can be tuned without paying for a new recording.

**Test 1, the radio cut** (narration over a temp drone on black, sent on WhatsApp):

- My siblings rewrote s05: *"ከእነሱ በኋላ ለሚመጡት ብለው፤ ያገኙትን ቆጠቡ"* ("For the ones who would come after them, they saved what they earned"). I used their words, and the dry run listed exactly one regeneration, `narration s05 (changed: text)`.
- A friend said the last shot did not look like the same woman as the shot before. I first re-prompted it with the previous shot as a reference. When the free image quota ran out (F21), I made the last shot *continue from the previous shot's own frame*: Wan animates her turning from the laptop to the window. She is now the same person by construction.
- A sibling said the film "has an emotional hook and a sentimental meaning". The structure stayed.
- A friend heard "some mispronunciations" but could not name the words. I recorded it as a limitation of the voice.

What I took from it: my family listened to the words more than they looked at the pictures. Two of the four notes were about language. The narration is the spine of a film like this, and native listeners are its most valuable reviewers.

**A change of mind of my own.** I added detailed family facts (a named street, decades, a government office), then went back to the first, simpler story, which is closer to how we tell it at home. Because the cache is keyed by content, going back cost one voice recording.

**Test 2, the near-final cut.** A native-speaker viewer said *"I really liked it … I really liked the ending of the story,"* and gave ten timestamped notes.
Mapped to the timeline, **7 of the 10 were the voice model misreading text that was correct in the storyboard**:
- pauses inside a phrase,
- "ቀን ቀን" read as "ቀን ገን",
- an extra "ማታ",
- a dropped syllable in "ሁላችንንም",
- sentence-final intonation where the clause continues.

Only 3 were script choices:
- "ስፌት በስፌት" (*stitch by stitch*) sounds like a duplication in Amharic,
- graduation should read as the payoff of her hard work, not "one day",
- the spoken form "ተመረኩ".

That turned test 1's vague "mispronunciations" into specifics, and it showed where the weak link is: Amharic TTS rendering, not the text.
I chose not to change this version because of the deadline. Each fix is contained: about 8 voice lines, with every image and clip reused from the cache. The real cost is a native re-listen of each new take. It is the first change in the next version (DESIGN.md, test 2).

## 3. The hardest problem and how I solved it

**Getting the free GPU to produce video at all, without letting it hold the film hostage.**

1. The official Wan 2.2 code needs FlashAttention 2, which Kaggle's T4 cannot run (F1), so I used the Diffusers pipeline instead.
2. The first job then ran out of memory: 15.0 GB on a 14.6 GB card (F15). I stored the 5-billion-parameter transformer's weights in fp8 and computed in fp16, moved the video decoder to Kaggle's second GPU, and encoded the prompts once in fp32 on the CPU. Peak memory fell to 7.3 GB. That headroom let me render at native 720p, at about 37 GPU-minutes per clip (E4, E8).
3. The stage never blocks the film. GPU jobs are submitted and fetched asynchronously, and any shot without a clip falls back to a Ken Burns move automatically.

When a clip came back wrong, the fallback paid off. My prompt said *"the camera rises"*, and the model put a camera in my hands (F17, E7). Rewording the prompt changed its cache key, so the film used the still for that shot until the new clip arrived.

Wan clips are 3.4 s but my shots run 6–11 s. Motion-compensated slow motion, then a hold that continues from the clip's last frame with the same crop, fit them without a frozen frame (F16).

The same pattern repeated with every free service. Most of my effort went into recovering when providers failed:

- Gemini answered "high demand" on 21 of 22 calls one afternoon.
- Hugging Face downloads stalled and left a full-size but corrupt file. I caught it by checking its SHA-256 (F18).
- The image quota ran out on deadline day (F21).

FAILURES.md has 21 entries. Each says what broke, what I tried, and what fixed it.

## 4. Suggested practices, tested honestly

**One that beat my instinct: the radio cut first, with narration setting the shot lengths.** My instinct was to make pictures first. Timing the narration first gave real numbers instead of guesses. The words-per-second estimate said 96.6 s; the measured Amharic narration gave 85.5 s, inside 60–90 s before a single image existed. It also exposed the voice problems while they were still cheap to fix, and it put the most important feedback (wording, voice) in front of my family first. Every shot's length is now derived from its measured line.

**One that did not work as suggested: "make a character sheet, then condition every keyframe on it".** Used literally, it backfired twice:

- The model copied the sheet's *layout* into scenes: 4 of 22 keyframes showed the same person twice, side by side (E3b).
- The sheets themselves drew non-Ethiopian faces and a European castle for Harar, because "warm brown skin" was not specific enough (E3a).

What worked was cropping each reference to exactly what should transfer (the portrait), naming the ethnicity and region explicitly, and grounding places in research and my own reference photos. The idea of a locked look was right. The literal recipe needed engineering.

## 5. Beyond the floor

- **Other languages (E12).** I narrated the opening and closing lines in Afaan Oromo and Tigrinya with Addis AI, and tried Harari, the language of the city in the film. Every call succeeded, but the "Harari" came back as mostly Amharic: no provider supports it. **A successful API response is not language support.** For a low-resource language, the pipeline can produce something that looks right to a non-speaker and is wrong.
- **A tool for families (E13).** The command `python -m pipeline draft-storyboard` turns a relative's plain-text story into a storyboard the pipeline can run. On a test story it was valid on the first round, with every family detail flagged for confirmation. It also **invented "In memory of our father"**, which the story never says. The schema guarantees shape, not truth, so a human fact check stays mandatory.
- **Measured choices instead of guesses.**
  - I picked the score by measuring the four candidates: only one builds toward the end, and it carries the least energy in the speech band (E10).
  - I measured ducking depth: the suggested setting pushed the music about 23 dB under the voice, so I chose a gentler one (E11).
  - Format changes kept approved looks through composition references (E5), with a per-shot vertical crop on a 16:9 master.
- **A showcase site** (`make site`) built from the pipeline's own records: every shot with its prompts, seed, crop and fact flags, and a run-log chart computed from `runs.jsonl`.

## 6. What I would build next

- A small web form in Amharic where a relative tells their story and gets a reviewed storyboard back, with the fact check (human plus the reviewer agent) built in and the end card as a template, not model text.
- An identity-consistency metric (face-embedding similarity to the approved reference) to replace judging consistency by eye.
- The test-2 fixes: three script edits and re-takes of five lines, each re-checked by a native listener. Then an automatic check, comparing a speech-to-text transcript of each take with its script, to catch repeated or dropped words before a person has to.
- Native-speaker review loops for Oromo and Tigrinya, and a consented native voice for Harari.
- A one-click "regenerate this shot" in the showcase site, since the pipeline already rebuilds exactly one shot per change.
