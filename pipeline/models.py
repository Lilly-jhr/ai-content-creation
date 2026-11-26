"""The storyboard contract.

These Pydantic models are the single source of truth for storyboard.json.
`schema/storyboard.schema.json` is generated from them (`python -m pipeline schema`)
and a test fails if the committed schema drifts from the models.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Id = Field(pattern=r"^[a-z0-9_]+$", min_length=2, max_length=40)
Ratio = Literal["9x16", "16x9"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactFlag(Strict):
    """Marks where a detail comes from, so nothing invented is presented as fact."""

    claim: str
    status: Literal["family-confirmed", "researched", "interpretation", "pending-family"]
    source: str | None = Field(None, description="Citation for researched claims, or who confirmed")


class Meta(Strict):
    title: str
    language: str = Field(description="BCP-47 code of the narration, e.g. 'am'")
    subtitle_language: str = "en"
    audience: str
    intent: str = Field(description="What the audience should feel or understand at the end")
    logline: str
    style_block: str = Field(description="Appended verbatim to every image prompt")
    negative_prompt: str = ""
    fps: int = 24
    loudness_lufs: float = -14.0
    true_peak_db: float = -1.0
    lead_in_s: float = Field(0.5, description="Silence before each narration line in its shot")
    tail_s: float = Field(0.9, description="Breathing room after each narration line")
    transition_s: float = Field(0.5, description="Dissolve length between shots")
    vo_tempo: float = Field(
        1.0, ge=0.75, le=1.25, description="Deterministic pitch-preserving tempo applied after TTS"
    )
    vo_warmth: bool = Field(True, description="Gentle low-mid lift / high softening on the voice")


class RefImage(Strict):
    prompt: str = Field(description="Reference-sheet prompt (style_block is appended)")
    seed: int
    width: int = 1024
    height: int = 1024
    approved_key: str | None = Field(None, description="Cache key of the approved reference image")


class Character(Strict):
    id: str = Id
    role: str = Field(description="Role, never a real name, e.g. 'great-grandmother, tailor'")
    chapter: int = Field(ge=1, le=5)
    age_range: str
    description: str = Field(description="Visual block reused verbatim in every prompt")
    wardrobe: str
    demeanour: str
    continuity_rules: list[str] = []
    ref: RefImage
    fact_flags: list[FactFlag] = []


class Location(Strict):
    id: str = Id
    era: str
    description: str = Field(description="Visual block reused verbatim in prompts")
    ref: RefImage | None = None
    fact_flags: list[FactFlag] = []


class Keyframe(Strict):
    prompt: str = Field(description="Shot-specific prompt; character/location blocks are prepended")
    seed: int
    width: int = 1024
    height: int = 1024
    use_refs: bool = Field(True, description="Condition on approved character/location references")
    composition_ref: str | None = Field(
        None,
        description="Repo-relative image whose composition/look to keep (e.g. an earlier approved frame)",
    )
    vertical_center: float = Field(
        0.5,
        ge=0.0,
        le=1.0,
        description="Where (fraction of width) the 9:16 crop is centred in the 16:9 master",
    )
    approved_key: str | None = None


class KenBurns(Strict):
    zoom_start: float = Field(1.0, ge=1.0, le=1.6)
    zoom_end: float = Field(1.12, ge=1.0, le=1.6)
    pan: Literal["none", "left", "right", "up", "down"] = "none"


class Motion(Strict):
    mode: Literal["auto", "wan", "kenburns", "still"] = Field(
        "auto", description="auto = Wan clip if cached, else Ken Burns"
    )
    prompt: str = Field("", description="Motion and camera only; the keyframe holds the subject")
    seed: int = 0
    targets: list[Ratio] = Field(default_factory=lambda: ["9x16"])
    frames: int = Field(81, ge=17, le=121)
    steps: int = Field(30, ge=4, le=60)
    kenburns: KenBurns = KenBurns()


class Narration(Strict):
    text: str = Field(description="Narration in meta.language")
    text_en: str = Field(description="English subtitle text")
    provider: Literal["addis", "gemini"] | None = None
    voice: str | None = None
    speed: float = Field(1.0, ge=0.5, le=1.5)
    style: str | None = Field(None, description="Delivery note (used by providers that support it)")


class Shot(Strict):
    id: str = Field(pattern=r"^s\d{2}$")
    seq: int = Field(ge=1)
    chapter: int = Field(ge=1, le=5, description="1 great-grandparents ... 5 me")
    purpose: str = Field(description="Why this shot exists")
    emotional_beat: str
    visual: str
    characters: list[str] = []
    location: str | None = None
    shot_size: Literal["extreme-wide", "wide", "medium", "medium-close", "close", "extreme-close"]
    angle: str = "eye-level"
    camera_move: str
    subject_move: str
    lighting: str
    composition: str = "subject centred, safe for 9:16 and 16:9 crops"
    transition_out: Literal["cut", "dissolve", "fade"] = "dissolve"
    min_duration_s: float = Field(5.0, ge=2.0, le=15.0)
    keyframe: Keyframe
    motion: Motion = Motion()
    narration: Narration | None = None
    music_cue: str | None = None
    ambience: str | None = None
    fact_flags: list[FactFlag] = []


class MusicCue(Strict):
    id: str = Id
    from_shot: str
    to_shot: str
    purpose: str


class Music(Strict):
    cues: list[MusicCue] = []
    caption: str
    lyrics: str = "[Instrumental]"
    bpm: int | None = Field(None, ge=30, le=300)
    keyscale: str | None = None
    timesignature: str | None = "4"
    duration_s: float = Field(95.0, ge=10, le=600)
    seeds: list[int] = Field(min_length=1)
    align: Literal["start", "end"] = Field(
        "end",
        description="end: skip the track's head so its ending (and build) lands on the film's ending",
    )
    chosen_seed: int | None = None
    why: str | None = Field(None, description="Why the chosen candidate won")


class EndCard(Strict):
    lines: list[str] = Field(min_length=1)
    duration_s: float = Field(3.0, ge=2.0, le=6.0)


class Storyboard(Strict):
    schema_version: Literal["1.0"] = "1.0"
    meta: Meta
    characters: list[Character] = []
    locations: list[Location] = []
    shots: list[Shot] = Field(min_length=8, max_length=12)
    music: Music
    end_card: EndCard

    @model_validator(mode="after")
    def _semantic_checks(self) -> Storyboard:
        errors: list[str] = []
        for label, ids in (
            ("character", [c.id for c in self.characters]),
            ("location", [loc.id for loc in self.locations]),
            ("shot", [s.id for s in self.shots]),
        ):
            dupes = {i for i in ids if ids.count(i) > 1}
            if dupes:
                errors.append(f"duplicate {label} ids: {sorted(dupes)}")
        seqs = [s.seq for s in self.shots]
        if seqs != sorted(seqs) or len(set(seqs)) != len(seqs):
            errors.append("shots must be listed in strictly increasing seq order")
        char_ids = {c.id for c in self.characters}
        loc_ids = {loc.id for loc in self.locations}
        shot_ids = {s.id for s in self.shots}
        for s in self.shots:
            missing = [c for c in s.characters if c not in char_ids]
            if missing:
                errors.append(f"{s.id}: unknown characters {missing}")
            if s.location and s.location not in loc_ids:
                errors.append(f"{s.id}: unknown location {s.location!r}")
        cue_ids = {c.id for c in self.music.cues}
        for s in self.shots:
            if s.music_cue and s.music_cue not in cue_ids:
                errors.append(f"{s.id}: unknown music cue {s.music_cue!r}")
        for c in self.music.cues:
            if c.from_shot not in shot_ids or c.to_shot not in shot_ids:
                errors.append(f"music cue {c.id}: unknown shot reference")
        if self.music.chosen_seed is not None and self.music.chosen_seed not in self.music.seeds:
            errors.append("music.chosen_seed must be one of music.seeds")
        planned = sum(s.min_duration_s for s in self.shots) + self.end_card.duration_s
        if not 45 <= planned <= 90:
            errors.append(f"planned runtime {planned:.1f}s is outside 45-90s (final target 60-90s)")
        if errors:
            raise ValueError("; ".join(errors))
        return self

    def shot(self, shot_id: str) -> Shot:
        for s in self.shots:
            if s.id == shot_id:
                return s
        raise KeyError(shot_id)

    def character(self, char_id: str) -> Character:
        return next(c for c in self.characters if c.id == char_id)

    def location(self, loc_id: str) -> Location:
        return next(loc for loc in self.locations if loc.id == loc_id)
