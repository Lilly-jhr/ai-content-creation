# DESIGN: audience, intent, and what the audience changed

> Written **before any image, clip or music was generated** (see the git history: this file and the storyboard
> draft precede the first `refs`/`keyframes` line in runs.jsonl).

## Brief
| | |
|---|---|
| **Film** | *A Little Further*: a 60–90 s heritage short, Amharic narration, English subtitles |
| **Who watches** | Primary: my family and relatives in Ethiopia and the diaspora. Secondary: peers and colleagues (Slack/LinkedIn) |
| **Where** | On a phone, vertical, forwarded in WhatsApp/Telegram family groups, often watched with the sound low |
| **One feeling at the end** | That one person's achievement is the accumulated sacrifice of many, and that the story isn't finished: it's my turn to take the family a little further |
| **How might we…** | …help my family see four generations of quiet sacrifice as one continuous story, in under 90 seconds, without inventing anything about them? |

### Design consequences
- **Vertical first** (the main graded file and how the family watches): subjects are centred, and subtitles sit above the bottom 20% UI zone.
- **Sound low / muted viewing**: English subtitles are burned in; the Amharic narration carries the emotion for family viewers.
- **No invented facts**: anything the family hasn't confirmed is framed as interpretation (fact_flags in `storyboard.json`), or the narration stays non-specific.
- **Not a tourism film**: no landmarks-for-their-own-sake. Harar appears only where the family's story touches it (the walls open and close the film).
- **Painterly, not photoreal**: these are AI *actors* standing in for real people, so it must never look like archival photographs.
- **Motif**: a thin green-and-gold thread bracelet worn in every generation. This is a creative interpretation (not a real heirloom unless the family names one); it ties tailoring (thread) to the later generations and gives the consistency system an anchor detail.

### Story revisions (producer decisions, 2026-11-26)
- After adding detailed family facts (a specific street, decades, a government office), the producer chose to **return to the first,
  less specific story**. She kept only two of the later facts: her own path (honours graduate, master's on scholarship, AI engineer in
  Addis Ababa) and her grandmother's **street-side stall**. A simpler, more universal story was preferred over a more documented one.
  Because the cache is keyed by text, reverting cost **one** TTS call (s09). The other 10 lines were reused.
- The film does not comment on family members' lives beyond the story itself (producer's wish).

## Ideation (alternatives considered)
1. **Chronological, four chapters** (chosen): simplest for a family audience; each chapter is 2–3 shots.
2. *Reverse chronology* (start with my graduation and look back): punchier opening, but risks centring me instead of them.
3. *One object across time* (a sewing machine handed down): strong, but it would invent an heirloom the family hasn't confirmed.

## Every shot has a reason
Each `shots[].purpose` in `storyboard.json` states why the shot exists. Here is the summary arc:

| Chapter | Shots | Beat |
|---|---|---|
| 1 Great-grandparents (immigrant tailors) | s01–s03 | humility, beginnings |
| 2 Grandparents (merchants) | s04–s05 | determination, building |
| 3 Mother (market + school → graduation) | s06–s08 | struggle, perseverance |
| 4 Mother raising me (office, long hours) | s09 | love, responsibility |
| 5 Me (SE with honours, AI) | s10–s11 | gratitude, possibility |

---

## User test 0: narrator voice (blind audition, 2026-11-25)
- **What:** the same opening line in 4 female Amharic voices (A–D, names hidden; `outputs/audition/blind/`).
- **Who:** the producer, her sisters and her friends (the film's primary audience).
- **Result:** voice **B** (`am-sara`, tagged "motherly, warm, inspiring") was chosen. Their note: *"a little fast, and it needs more warmth."*
- **What changed:** every line now uses `am-sara`. The provider's speed setting turned out to be ignored (EXPERIMENTS E1b), so the
  voice is slowed (×0.9) and warmed deterministically in our own pipeline (`meta.vo_tempo`, `meta.vo_warmth`).

## User test 1: radio cut (2026-11-26)
**What they saw:** `outputs/final/radio_cut.mp4` (85.5 s; Amharic narration over a temp drone on black, English subtitles), sent on WhatsApp.
**Who:** the producer's siblings and friends: the film's primary audience (family) plus peers.

| # | Who (relationship) | What they said | What changed |
|---|---|---|---|
| 1 | siblings | s05 should say **"ከእነሱ በኋላ ለሚመጡት ብለው፤ ያገኙትን ቆጠቡ"**, putting "for the ones who would come after them" first | `shots[s05].narration.text` replaced with their wording, and `text_en` re-ordered to match ("For the ones who would come after them, they saved what they earned."). Only s05's narration regenerates (dry run: `GENERATE narration s05 changed: text`) |
| 2 | a friend | "there are some mispronunciations" (general; no specific words when asked) | not actionable without the words. Recorded as a limitation of the Addis voice. The fix path, if specific words come up in test 2, is phonetic respelling in `narration.text`, which regenerates only those lines |
| 3 | a friend | the s11 image (on the balcony) isn't consistent with the s10 character | First attempt: s11 re-prompted with s10's wardrobe and hair, with the s10 frame as an extra reference (`keyframe.extra_refs`). Blocked by the image quota (FAILURES F21). **Final:** s11 now *continues from s10's own frame* (`keyframe.source_shot: s10`). Wan animates her turning from the laptop to the window and the city, so she is the same person by construction |
| 4 | a sibling | "the content has an emotional hook and a sentimental meaning" | no change: confirms the intent stated above. The story structure is kept |

**Insight:** the family heard the words more than the pictures. Two of the four notes were about *language*: word order in s05, and pronunciation.
The narration is the spine, so native listeners are the most valuable reviewers, as the brief predicted ("names and places are where TTS goes wrong").

## User test 2: near-final cut (2026-11-26)
**What they saw:** the near-final vertical film (85.5 s; 6 Wan shots, 5 Ken Burns, chosen score, gentle ducking), sent by the producer.
**Response recorded here:** one detailed, timestamped written review from a native Amharic speaker in the audience (shared by the producer; relationship not recorded).
Overall: *"I really liked it!"* … *"I really liked the ending of the story."*

The timestamps map onto the measured timeline (`outputs/timeline.json`). I classified each note by cause:

| Time | Shot | What they said | Cause | Text in the storyboard |
|---|---|---|---|---|
| 00:15 | s03 | long gap between "ልብስ ሰፊዎች" and "ነበሩ" | **TTS rendering** (pause inside a phrase) | correct |
| 00:16 | s03 | word duplication "ስፌት በስፌት" | **script choice**: the intended "stitch by stitch" reads as an error to a native ear | as written |
| 00:22 | s04 | long gap between "መንገድ" and "ዳር" | **TTS rendering** | correct |
| 00:29 | s05 | "ብለው" read as sentence-final; it should rise into the next word | **TTS prosody**, triggered by the `፤` after ብለው | punctuation |
| 00:34 | s06 | "ቀን ገን" should be "ቀን ቀን" | **TTS mispronunciation** | correct (ቀን ቀን) |
| 00:40 | s07 | "ማታ ማታ ማታ" has an extra "ማታ" | **TTS repetition** (hallucinated word) | correct (ማታ ማታ) |
| 00:43 | s07 | "ነበር" should have a final, narrating tone | **TTS prosody** | correct |
| 00:46 | s08 | replace "አንድ ቀንም" with a line about the day her hard work paid off, e.g. "ልፋትዋን የምታይበትም ቀን ደረሰና" | **script / meaning**: graduation as payoff, not a one-off event | script |
| 01:02 | s10 | "ተመረቅሁ" should be "ተመረኩ" | **script register** (spoken form) | script |
| 01:17 | s11 | "ሁላችንም" should be "ሁላችንንም" | **TTS dropped a syllable** | correct (ሁላችንንም) |

**Insights:**
- **7 of 10 problems are the voice model misreading text that is correct in the storyboard.** Only 3 are script choices. Test 1's general note,
  "some mispronunciations", now has specifics. The text pipeline (translation, glossary, review) held up; the weakest link is Amharic TTS rendering:
  pauses, a repeated word, a dropped syllable, and sentence-final intonation where a clause continues.
- A native ear rejects rhetorical repetition ("ስፌት በስፌት") that reads well in English ("stitch by stitch"). Translation needs a native *listener*, not only a reader.
- The ending landed ("I really liked the ending"), so the s11 continuity change from test 1 worked.

**What changed: nothing in this version (producer's decision, deadline).** The fix is cheap and contained:
1. Script edits in `narration.text` for s03, s08 and s10, and `፤` → `፣` after "ብለው" in s05.
2. Re-takes of the TTS-error lines (s03, s04, s06, s07, s11). TTS is stochastic, so a re-take changes the take, and each needs a native re-listen.
3. `make film`: per the cache design, only those narration lines and the edit regenerate (about 8 Addis calls, no images or clips).

The bottleneck is native verification of each re-take, not compute. This is the first change in the next version.

*Coverage note: the brief asks for ≥3 people per test; this section records one written response. Any further test-2 replies go in the table above.*
