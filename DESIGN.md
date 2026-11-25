# DESIGN: audience, intent, and what the audience changed

> Written **before any image, clip or music was generated** (see the git history: this file and the storyboard
> draft precede the first `refs`/`keyframes` line in runs.jsonl).

## Brief
| | |
|---|---|
| **Film** | *A Little Further*: a 60–90 s heritage short, Amharic narration, English subtitles |
| **Who watches** | Primary: my family and relatives in Ethiopia and the diaspora. Secondary: peers and colleagues (Slack/LinkedIn) |
| **What it is** | A tribute to my late mother and the generations before her (updated 2026-11-25 when I told the agent she has passed away; this changes the tone of the ending, see open question below) |
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

### Open question (producer to decide): how the film acknowledges her passing
- (a) Leave the narration as is and change the end-card dedication to "In loving memory of my mother."
- (b) Add one short line in s09/s10, e.g. "She did not live to see where it led", **only if** the producer wants it and the family approves.
- (c) Don't mention it at all; the film simply honours her.
The current draft is (c), with the dedication "For my mother, and everyone before her."

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

## User test 1: radio cut (narration + temp music on black, with subtitles)
*Status: pending. The radio cut is sent to ≥3 people from the audience; replies are recorded verbatim here.*

| # | Who (relationship, no names) | Watched on | What they said (verbatim / close paraphrase) | Where they reacted |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Insights → storyboard changes** (each linked to a commit):
- …

## User test 2: near-final cut
*Status: pending.*

| # | Who | Watched on | What they said | Where they reacted |
|---|---|---|---|---|
| 1 | | | | |
| 2 | | | | |
| 3 | | | | |

**Insights → changes:**
- …
