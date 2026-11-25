# ETHICS: consent, privacy, labelling, licences

## 1. Consent record
**Gate:** nothing depicting or voicing a real person is generated before their row below is complete.

Approach: no real faces, photographs or voices are used. Every person is represented by a **fictional,
painterly AI actor**, and the narration uses a **stock TTS voice** (no voice cloning). The film is still about
real people, so informed consent to the story and to the words spoken about them is recorded.

| Person (role) | Alive | What is depicted / said | Consent given by | How recorded | Date | Words approved? |
|---|---|---|---|---|---|---|
| Me (narrator, her daughter) | yes | fictional AI actor (young woman); lines s10–s11; first-person narration in a stock female voice (Addis `am-sara`), not my own voice | myself | this file | 2026-11-25 | yes |
| Mother | n/a | fictional AI actor, **not her likeness** (no photos used); her voice is never used or imitated; lines s06–s09 describe her work in the market while studying, her graduation and her long office hours, in my words as her daughter | **her daughters (my sisters and me), as next of kin** | consent given to me by my sisters; the record is kept privately by me, not in the repo | 2026-11-25/26 | my sisters are also radio-cut testers and hear every line before release (DESIGN.md test 1) |
| Great-grandparents (immigrant tailors) | n/a | fictional AI actors; immigrant tailors (s02–s03) | my sisters and me, as descendants, on the family's behalf | as above | 2026-11-25/26 | as above |
| Grandmother (street-side stall merchant) | n/a | fictional AI actor; her stall (s04–s06) | my sisters and me, on the family's behalf | as above | 2026-11-25/26 | as above |

Informed means the person (or their next of kin) knew: it's AI-generated, it will be posted
publicly with an AI label, the exact narration lines, and that they can ask for changes or removal.

### Consent given by next of kin
Where a family member cannot give consent themselves, consent is given by next of kin. Because of this, every
family member is represented by a **fictional, painterly AI actor**, never by their face, photographs or voice:
1. **Next-of-kin permission:** close family agree to the story being told publicly in this form and hear the lines about them.
2. **The narrator's standing:** the narration is my account of my own family, in my own words. It does not put words in anyone's mouth.
3. **No likeness, no voice:** no photographs as references, no voice cloning, nothing that could pass as a real recording.
4. **Accuracy:** only facts the family confirms are stated as fact (`fact_flags`). Everything else is marked as interpretation.
5. **Right to withdraw:** if any family member objects after release, the post is edited or taken down.

## 2. Privacy
- No real names, dates, addresses or private family details in any prompt. Prompts use role ids (`mother`, `gen1_tailor_m`).
- The Gemini API free tier may use inputs to improve Google products, and human reviewers may read them.
  Only non-private text goes to Gemini. Addis AI states API inputs are not used to train its base models.
- Family photographs, if shared, stay local as private reference and are not uploaded to free endpoints without explicit approval.

## 3. Labelling and provenance
- **End card** (in the film): "Made with AI: characters and scenes are AI-generated, not real photographs", followed by the models used.
- **Posting:** the platform's AI-content label is switched on (YouTube "altered or synthetic content" / TikTok "AI-generated" / Meta "AI info").
- **Provenance:** no watermark removal. Gemini TTS output carries SynthID (if used). Generated files keep their metadata,
  and every asset has a `.meta.json` sidecar recording model, prompt, seed and run id.
- **Style:** described by qualities (painterly, gouache, warm palette), never by a living artist's name.

## 4. Licence register
| Component | Used for | Licence / terms | Commercial use of output | Checked |
|---|---|---|---|---|
| FLUX.2 klein **4B** (`@cf/black-forest-labs/flux-2-klein-4b`) via Cloudflare Workers AI | refs, keyframes | Apache-2.0 weights; Cloudflare Workers AI terms; BFL terms for hosted use | Yes (Apache-2.0); hosted-output terms unverified | 2026-11-25 |
| FLUX.2 klein 9B | **not used** | FLUX Non-Commercial License | No | 2026-11-25 |
| FLUX.1 schnell (fallback) | keyframes if klein fails | Apache-2.0 | Yes | 2026-11-25 |
| Wan 2.2 TI2V-5B (Diffusers) | image-to-video on Kaggle | Apache-2.0 | Yes | 2026-11-25 |
| ACE-Step 1.5 | score | MIT; model card states outputs usable commercially | Yes | 2026-11-25 |
| Addis AI TTS | Amharic narration | Addis AI API terms: commercial use allowed, inputs not used for training (FAQ) | Yes (FAQ); ownership terms unverified | 2026-11-25 |
| Gemini 3.8 Flash TTS / Gemini Flash-Lite | backup TTS; drafting and translation | Gemini API Terms (Google does not claim ownership of outputs) | Yes | 2026-11-25 |
| HunyuanVideo 1.5 | **not used** | Tencent Hunyuan Community License (excludes EU/UK/KR) | n/a | 2026-11-25 |
| Noto Sans, Noto Sans Ethiopic | subtitles, end card | SIL Open Font License 1.1 (`fonts/OFL.txt`) | Yes | 2026-11-25 |
| FFmpeg | assembly | LGPL/GPL (system install, not redistributed) | n/a | 2026-11-25 |
| Kaggle notebooks | GPU compute | Kaggle terms | n/a | 2026-11-25 |

I'm not a lawyer. Uncertain items are marked "unverified" and would be checked before any commercial use.
