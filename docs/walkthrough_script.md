# Walkthrough recording script (target 4:55, limit 5:00)

| Part | Time | Covers (the brief's three requirements) |
|---|---|---|
| Intro | 0:00–0:15 | what the film is |
| **Architecture** | 0:15–1:45 (1:30) | storyboard.json as the contract → the stages → caching → logging |
| **One hard decision** | 1:45–2:45 (1:00) | the problem, what I chose, why |
| **Live regeneration** | 2:45–4:35 (1:50) | edit one narration line → only that shot regenerates → one new log line |
| Close | 4:35–4:55 | what I learned |

The live demo applies a real fix from user test 2: in s05, "ብለው" was read as sentence-final. Changing `፤` to `፣` tells the voice
the clause continues. Only s05's narration regenerates. Every image, clip and other line is reused from the cache.

## Before you hit record (5 min of prep)
1. Terminal font about 18 pt, VS Code zoom about 125%. Close other tabs. **Never open `.env` on screen.**
2. Open these tabs in VS Code, in this order:
   - `storyboard.json` (line 564)
   - `ARCHITECTURE.md` (the diagram at the top)
   - `pipeline/core/calls.py` (line 61)
   - `FAILURES.md` (line 82)
   - `kaggle/wan_i2v/run.py` (line 92)
3. In the terminal: `cd` into the repo and run `clear`.
4. In the browser, open the showcase site (https://claude.ai/artifact/AH52udg1c4XJBsTFEzzshW) at the top. Also have
   `outputs/final/a_little_further_9x16.mp4` ready in a video player.
5. Check the internet works. The live step makes one Addis AI call.
6. Rehearse the commands once **without** saving the edit, so the real edit happens on camera.

You can pause the recording while a command runs. The brief allows it.

---

## 0:00–0:15 · What this is (browser: the site)
**Show:** the site hero. Press play on the vertical film for about 5 seconds, then pause.
**Say:**
> "This is *A Little Further*, an 85-second film in Amharic about four generations of my family, from great-grandparents who were tailors in Harar to me, an AI engineer.
> Nothing in it was edited by hand. One file drives a pipeline that makes every image, clip, voice line and note of music, and assembles them."

## 0:15–1:45 · The architecture (VS Code)
**Show `storyboard.json`, scrolled to shot s05 (line 522).** Point at `purpose`, `keyframe.prompt` + `seed`, `motion`, `narration.text` (Amharic) + `text_en`, and `fact_flags`.
> "This is the contract. Every shot has a reason to exist, its prompts and seeds, its Amharic line and English subtitle, and a fact flag that says whether
> the family confirmed it. It's validated by Pydantic models before every stage."

**Show `ARCHITECTURE.md`, the diagram.**
> "Eight stages: translation draft, narration, subtitles, reference sheets, keyframes, Wan video on Kaggle, the ACE-Step score, and an FFmpeg-only edit."

**Show `pipeline/core/calls.py`, line 61 (`call_model`).**
> "**Caching:** every model call goes through this one function. It hashes exactly the inputs that asset depends on (prompt, seed, model, and the hashes
> of upstream assets) into a cache key. If a file with that key exists, it is reused. So if I change one shot, only that shot regenerates, and anything
> downstream of it. Next to every asset is a small sidecar file saying exactly how it was made."
> "**Logging:** every attempt, success or failure, writes one line to runs.jsonl. Retries for temporary errors happen here too."

**Terminal:**
```bash
wc -l runs.jsonl
tail -1 runs.jsonl | python3 -m json.tool | head -20
```
> "227 calls so far, failures included. Each records the model, prompt, seed, latency and status."

## 1:45–2:45 · One hard decision: video on a free GPU (VS Code)
**Show `FAILURES.md`, line 82 (F15).**
> "The hardest problem was running Wan 2.2 on Kaggle's free T4. The official code needs FlashAttention, which the T4 can't run, so I used Diffusers.
> The first job ran out of memory: 15 gigabytes on a 14.6 gigabyte card."

**Show `kaggle/wan_i2v/run.py`, lines 92–101.**
> "The fix was to store the weights in fp8, compute in fp16, and decode on Kaggle's second GPU. Peak memory dropped to 7.3 gigabytes, which let me render at 720p.
> The bigger decision was that the film never waits for the GPU. If a clip is missing, the edit falls back to a slow pan and zoom automatically.
> When one clip came back with a camera in my hands, because my prompt said 'the camera rises', the film used the still until the fixed clip arrived."

## 2:45–4:35 · Live: change one line, only that shot regenerates
> "In my second user test, a native speaker said that in shot 5 the word 'ብለው' sounded like the end of a sentence. I'll fix that now."

**1. Edit, in `storyboard.json` line 564.** Change the `፤` after **ብለው** to `፣`:
```
"text": "ከእነሱ በኋላ ለሚመጡት ብለው፣ ያገኙትን ቆጠቡ።",
```
Save. (The next command validates the storyboard before doing anything else.)

**2. Dry run (terminal):**
```bash
make dry-run
```
**Point at:** a single `GENERATE narration s05 … changed: text`. Everything else says `REUSE`.
> "The dry run names exactly what will change and why: one narration line, because its text changed. Every image, clip and other line is reused."

**3. Regenerate (terminal; you can pause the recording while it runs):**
```bash
wc -l runs.jsonl
make film
wc -l runs.jsonl
tail -1 runs.jsonl | python3 -m json.tool | grep -E '"stage"|"shot_id"|"model"|"status"|"latency_s"'
```
**Point at:**
- the `[film] model assets: … reused from cache, 1 generated` line,
- `runs.jsonl` growing by one line (or a few, if Addis needed a retry; each attempt is logged),
- the last line: `"stage": "narration"`, `"shot_id": "s05"`, `"status": "ok"`.
> "One model call. The edit itself is deterministic FFmpeg, so it rebuilds without calling any model."

**4. Play the result:** open `outputs/final/a_little_further_9x16.mp4` and jump to **0:27** (s05).
> "And now 'ብለው' leads into the rest of the sentence."

## 4:35–4:55 · Close (browser: the site, the "What we learned" section)
> "What I learned: a successful API call is not proof. The voice service ignored its speed setting, a 'Harari' voice was really Amharic, and
> in the last test 7 of 10 problems were the voice misreading correct text. So I measure the output, and I put the logs and the failures on the record
> alongside the film."

---

## Recording and sharing
- **Recorder:** OBS Studio (Fedora: `flatpak install flathub com.obsproject.Studio`). Add the "Screen Capture (PipeWire)" source and your microphone,
  record at 1920×1080, and check the mic level before starting. GNOME's built-in recorder (Ctrl+Shift+Alt+R) doesn't capture your voice.
- **Pauses:** pause OBS while `make film` runs. Cut anything over 5:00 before uploading.
- **Link that opens without a login:** YouTube upload as **Unlisted**, or Google Drive with **"Anyone with the link: Viewer"**. Test the link in a private window.

## After recording
```bash
git add -A && git commit -m "Test-2 fix (live in walkthrough): s05 punctuation so ብለው continues the clause" && git push
```
Then add one line to DESIGN.md test 2: *"s05 `፤`→`፣` applied live in the walkthrough."* (Or tell me and I'll do it.)

**If Addis fails on camera:** pause, run `uv run python -m pipeline narration` again. It retries only s05, because the other lines are cached.
