"""Stage: assemble. Deterministic FFmpeg edit from the storyboard + timeline. No AI here.

Picture: per-shot segments (Wan clip if cached for that ratio, else Ken Burns over the keyframe,
else a labelled placeholder), joined with dissolves at the timeline's cut points, subtitles
burned in, AI end card last.
Sound: narration placed at measured offsets, score pre-levelled and ducked under the voice
with sidechaincompress, then a two-pass loudnorm to -14 LUFS / -1 dBTP.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from pipeline.core import config, media
from pipeline.core.hashing import hash_file, hash_obj
from pipeline.models import Shot, Storyboard
from pipeline.stages import keyframes as kf_stage

SIZES = {"16x9": (1920, 1080), "9x16": (1080, 1920)}
TMP = config.OUTPUTS / "_tmp" / "assemble"
FINAL = config.OUTPUTS / "final"

# Edit parameters live here (and in the storyboard); they are part of every render hash.
EDIT: dict[str, Any] = {
    "crf": 18,
    "preset": "medium",
    "head_trim_s": 0.25,  # Wan clips often have a weak first frames
    "cut_s": 1 / 24,
    "vo_lufs": -16.0,
    "music_lufs": -24.0,
    "duck": {"threshold": 0.02, "ratio": 6, "attack": 300, "release": 1500},
    "music_fade_in_s": 2.0,
    "music_fade_out_s": 3.5,
    "tp_limit_lin": 0.83,  # about -1.6 dBFS before AAC encoding (F13)
    "kb_oversample": 2,
    "vertical_from_wide_clip": True,  # producer decision: master in 16:9, cut 9:16 from it
}


# ---------------------------------------------------------------- picture ---


def _transition(shot: Shot, sb: Storyboard) -> tuple[str, float]:
    if shot.transition_out == "cut":
        return "fade", EDIT["cut_s"]
    if shot.transition_out == "fade":
        return "fadeblack", max(sb.meta.transition_s, 0.8)
    return "fade", sb.meta.transition_s


def _font(size: int, ethiopic: bool = False) -> ImageFont.FreeTypeFont:
    names = (
        ["NotoSansEthiopic-Regular.ttf", "NotoSansEthiopic[wdth,wght].ttf"]
        if ethiopic
        else ["NotoSans-Regular.ttf", "NotoSans[wdth,wght].ttf"]
    )
    for n in names:
        if (config.FONTS / n).exists():
            return ImageFont.truetype(str(config.FONTS / n), size)
    fallback = "/usr/share/fonts/google-droid-sans-fonts/DroidSansEthiopic-Regular.ttf"
    if ethiopic and Path(fallback).exists():
        return ImageFont.truetype(fallback, size)
    return ImageFont.load_default(size)


def _is_ethiopic(text: str) -> bool:
    return bool(re.search(r"[ሀ-፿]", text))


def render_card(lines: list[str], size: tuple[int, int], out: Path, small: bool = False) -> Path:
    """Plain text card (end card or placeholder), rendered with Pillow so no AI text is involved."""
    w, h = size
    img = Image.new("RGB", size, (14, 12, 10))
    draw = ImageDraw.Draw(img)
    base = int(min(w, h) * (0.032 if small else 0.045))
    max_w = int(w * 0.84)
    y_total = 0
    rendered = []
    for i, para in enumerate(lines):
        font = _font(int(base * (1.35 if i == 0 and not small else 1.0)), _is_ethiopic(para))
        words, line = para.split(), ""
        wrapped = []
        for word in words:  # wrap by measured pixel width so text stays inside the frame
            trial = f"{line} {word}".strip()
            if draw.textlength(trial, font=font) <= max_w or not line:
                line = trial
            else:
                wrapped.append(line)
                line = word
        wrapped.append(line)
        for j, text in enumerate(wrapped):
            box = draw.textbbox((0, 0), text, font=font)
            rendered.append((text, font, box, i))
            gap = int(base * (0.25 if j < len(wrapped) - 1 else 0.8))
            y_total += (box[3] - box[1]) + gap
    y = (h - y_total) // 2
    for k, (text, font, box, para) in enumerate(rendered):
        tw = box[2] - box[0]
        colour = (236, 226, 208) if para == 0 else (190, 180, 165)
        draw.text(((w - tw) // 2 - box[0], y - box[1]), text, font=font, fill=colour)
        last_in_para = k == len(rendered) - 1 or rendered[k + 1][3] != para
        y += (box[3] - box[1]) + int(base * (0.8 if last_in_para else 0.25))
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def _kenburns_filter(shot: Shot, ratio: str, frames: int) -> str:
    w, h = SIZES[ratio]
    kb = shot.motion.kenburns
    zs, ze = kb.zoom_start, kb.zoom_end
    if kb.pan != "none" and max(zs, ze) < 1.06:
        zs = ze = 1.1  # panning needs slack inside the frame
    r = w / h  # largest crop of the target aspect, whatever the source aspect (16:9 master)
    c = shot.keyframe.vertical_center if ratio == "9x16" else 0.5
    crop = (
        f"crop='min(iw,ih*{r:.6f})':'min(ih,iw/{r:.6f})':"
        f"'max(0,min(iw-ow,{c}*iw-ow/2))':'(ih-oh)/2'"
    )
    ow, oh = w * EDIT["kb_oversample"], h * EDIT["kb_oversample"]
    n = max(frames - 1, 1)
    z = f"{zs}+({ze}-{zs})*on/{n}"
    sx, sy = "(iw-iw/zoom)", "(ih-ih/zoom)"
    x = {"left": f"{sx}*(1-on/{n})", "right": f"{sx}*on/{n}"}.get(kb.pan, f"{sx}/2")
    y = {"up": f"{sy}*(1-on/{n})", "down": f"{sy}*on/{n}"}.get(kb.pan, f"{sy}/2")
    return (
        f"{crop},"
        f"scale={ow}:{oh}:flags=lanczos,"
        f"zoompan=z='{z}':x='{x}':y='{y}':d={frames}:s={w}x{h}:fps=24,"
        "setsar=1,format=yuv420p"
    )


def segment_source(
    sb: Storyboard, shot: Shot, ratio: str, allow_draft: bool
) -> tuple[str, Path | None]:
    from pipeline.stages import video as video_stage  # local import: video imports keyframes

    if shot.motion.mode in ("auto", "wan"):
        clip = video_stage.cached_clip(sb, shot, ratio)
        if not clip and ratio == "9x16" and EDIT["vertical_from_wide_clip"]:
            clip = video_stage.cached_clip(sb, shot, "16x9")  # 16:9 master, centre-cropped
        if clip:
            return "wan", clip
    kf = kf_stage.current_path(sb, shot, require_approved=not allow_draft)
    if kf:
        return ("still" if shot.motion.mode == "still" else "kenburns"), kf
    return "placeholder", None


def render_segment(
    sb: Storyboard, shot: Shot, ratio: str, length: float, allow_draft: bool
) -> tuple[Path, str]:
    w, h = SIZES[ratio]
    frames = max(int(round(length * 24)), 2)
    kind, src = segment_source(sb, shot, ratio, allow_draft)
    spec = {
        "kind": kind,
        "src": hash_file(src) if src else None,
        "len": round(length, 3),
        "ratio": ratio,
        "kb": shot.motion.kenburns.model_dump(),
        "vcenter": shot.keyframe.vertical_center if ratio == "9x16" else 0.5,
        "edit": EDIT,
        "visual": shot.visual if kind == "placeholder" else None,
    }
    out = TMP / ratio / f"{shot.id}_{hash_obj(spec)}.mp4"
    if out.exists():
        return out, kind
    out.parent.mkdir(parents=True, exist_ok=True)
    common = ["-r", "24", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-an"]
    if kind == "wan":
        avail = media.duration(src) - EDIT["head_trim_s"]
        slow = min(1.35, length / avail) if length > avail else 1.0
        vf = (
            f"trim=start={EDIT['head_trim_s']},setpts=PTS-STARTPTS,setpts={slow:.4f}*PTS,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase:flags=lanczos,"
            f"crop={w}:{h}:'max(0,min(iw-ow,{shot.keyframe.vertical_center if ratio == '9x16' else 0.5}*iw-ow/2))':'(ih-oh)/2',"
            f"fps=24,tpad=stop_mode=clone:stop_duration={length:.3f},trim=duration={length:.3f},"
            "setsar=1,format=yuv420p"
        )
        media.run(["-i", str(src), "-vf", vf, *common, str(out)])
    elif kind in ("kenburns", "still"):
        if kind == "still":
            shot = shot.model_copy(deep=True)
            shot.motion.kenburns.zoom_start = shot.motion.kenburns.zoom_end = 1.0
            shot.motion.kenburns.pan = "none"
        vf = _kenburns_filter(shot, ratio, frames)
        media.run(["-i", str(src), "-vf", vf, "-frames:v", str(frames), *common, str(out)])
    else:
        card = render_card(
            [f"{shot.id}  (keyframe pending)", shot.visual[:70]],
            (w, h),
            out.with_suffix(".png"),
            small=True,
        )
        media.run(
            [
                "-loop",
                "1",
                "-i",
                str(card),
                "-t",
                f"{length:.3f}",
                "-vf",
                "format=yuv420p",
                *common,
                str(out),
            ]
        )
    return out, kind


def render_picture(
    sb: Storyboard, timeline: dict[str, Any], ratio: str, allow_draft: bool
) -> tuple[Path, dict]:
    w, h = SIZES[ratio]
    segs: list[Path] = []
    trans: list[tuple[str, float]] = []
    kinds: dict[str, str] = {}
    for shot, t in zip(sb.shots, timeline["shots"], strict=True):
        name, tdur = _transition(shot, sb)
        seg, kind = render_segment(sb, shot, ratio, t["duration"] + tdur, allow_draft)
        segs.append(seg)
        trans.append((name, tdur))
        kinds[shot.id] = kind
    end_png = render_card(
        sb.end_card.lines, (w, h), TMP / ratio / f"endcard_{hash_obj(sb.end_card.lines)}.png"
    )
    end = TMP / ratio / f"endcard_{hash_obj([sb.end_card.model_dump(), EDIT])}.mp4"
    if not end.exists():
        media.run(
            [
                "-loop",
                "1",
                "-i",
                str(end_png),
                "-t",
                f"{sb.end_card.duration_s:.3f}",
                "-vf",
                "format=yuv420p",
                "-r",
                "24",
                "-c:v",
                "libx264",
                "-crf",
                "16",
                str(end),
            ]
        )
    segs.append(end)

    args: list[str] = []
    for s in segs:
        args += ["-i", str(s)]
    chain, prev = [], "[0:v]"
    starts = [t["start"] for t in timeline["shots"]] + [timeline["end_card"]["start"]]
    for i in range(1, len(segs)):
        name, tdur = trans[i - 1]
        label = f"[x{i}]"
        chain.append(
            f"{prev}[{i}:v]xfade=transition={name}:duration={tdur:.4f}:offset={starts[i]:.4f}{label}"
        )
        prev = label
    subs = config.OUTPUTS / "subs" / f"{ratio}.ass"
    sub_filter = ""
    if subs.exists():
        sub_filter = f",subtitles=filename={subs.relative_to(config.ROOT)}:fontsdir=fonts"
    chain.append(f"{prev}format=yuv420p{sub_filter}[vout]")
    picture_key = hash_obj(
        [[hash_file(s) for s in segs], starts, trans, hash_file(subs) if subs.exists() else None]
    )
    out = TMP / ratio / f"picture_{picture_key}.mp4"
    if not out.exists():
        media.run(
            [
                *args,
                "-filter_complex",
                ";".join(chain),
                "-map",
                "[vout]",
                "-r",
                "24",
                "-c:v",
                "libx264",
                "-preset",
                EDIT["preset"],
                "-crf",
                str(EDIT["crf"]),
                "-an",
                str(out),
            ]
        )
    return out, kinds


# ------------------------------------------------------------------ sound ---


def placeholder_music(total: float, out: Path) -> Path:
    """Temp track for the radio cut: a quiet, slowly breathing A-minor drone."""
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        expr = "0.18*sin(2*PI*110*t)+0.12*sin(2*PI*164.81*t)+0.10*sin(2*PI*220*t)+0.06*sin(2*PI*261.63*t)"
        media.run(
            [
                "-f",
                "lavfi",
                "-i",
                f"aevalsrc='{expr}':s=48000:d={total + 1:.2f}",
                "-af",
                "tremolo=f=0.15:d=0.5,lowpass=f=1200,volume=0.6",
                "-ac",
                "2",
                str(out),
            ]
        )
    return out


def _loudnorm_two_pass(src: Path, dst: Path, lufs: float, tp: float) -> dict[str, Any]:
    proc = media.run(
        [
            "-i",
            str(src),
            "-af",
            f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json",
            "-f",
            "null",
            "-",
        ],
        quiet=False,
    )
    measured = json.loads(proc.stderr[proc.stderr.rindex("{") : proc.stderr.rindex("}") + 1])
    media.run(
        [
            "-i",
            str(src),
            "-af",
            f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={measured['input_i']}:"
            f"measured_TP={measured['input_tp']}:measured_LRA={measured['input_lra']}:"
            f"measured_thresh={measured['input_thresh']}:offset={measured['target_offset']}:linear=true,"
            # AAC encoding overshoots; a 4x-oversampled limiter keeps the delivered true peak <= -1 dBTP
            f"aresample=192000,alimiter=limit={EDIT['tp_limit_lin']}:attack=1:release=50:level=false,aresample=48000",
            "-ar",
            "48000",
            "-ac",
            "2",
            str(dst),
        ]
    )
    return measured


def render_mix(sb: Storyboard, timeline: dict[str, Any], music: Path | None) -> Path:
    total = timeline["total"]
    vo = [(config.ROOT / s["vo_path"], s["vo_start"]) for s in timeline["shots"] if s["vo_path"]]
    if music is None:
        music = placeholder_music(total, TMP / f"temp_music_{total:.2f}.wav")
    spec = [
        [(hash_file(p), st) for p, st in vo],
        hash_file(music),
        total,
        EDIT,
        sb.meta.loudness_lufs,
    ]
    out = TMP / f"mix_{hash_obj(spec)}.wav"
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        return out
    args: list[str] = []
    parts = []
    for i, (p, st) in enumerate(vo):
        args += ["-i", str(p)]
        ms = int(round(st * 1000))
        parts.append(
            f"[{i}:a]aresample=48000,aformat=channel_layouts=stereo,adelay={ms}|{ms}[v{i}]"
        )
    if not vo:  # nothing narrated yet: a silent voice bus keeps the graph identical
        args += ["-f", "lavfi", "-t", f"{total:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
        parts.append("[0:a]anull[v0]")
    m = max(len(vo), 1)
    args += ["-i", str(music)]
    d = EDIT["duck"]
    vo_mix = "".join(f"[v{i}]" for i in range(m))
    parts += [
        f"{vo_mix}amix=inputs={m}:normalize=0,apad=whole_dur={total:.3f},"
        f"loudnorm=I={EDIT['vo_lufs']}:TP=-2[vo]",
        "[vo]asplit=2[vo_sc][vo_mix]",
        f"[{m}:a]aresample=48000,aformat=channel_layouts=stereo,atrim=0:{total:.3f},"
        f"loudnorm=I={EDIT['music_lufs']}:TP=-3,"
        f"afade=t=in:d={EDIT['music_fade_in_s']},"
        f"afade=t=out:st={total - EDIT['music_fade_out_s']:.3f}:d={EDIT['music_fade_out_s']}[mus]",
        f"[mus][vo_sc]sidechaincompress=threshold={d['threshold']}:ratio={d['ratio']}:"
        f"attack={d['attack']}:release={d['release']}[ducked]",
        f"[ducked][vo_mix]amix=inputs=2:normalize=0,atrim=0:{total:.3f}[mix]",
    ]
    pre = out.with_name(out.stem + "_pre.wav")
    media.run(
        [*args, "-filter_complex", ";".join(parts), "-map", "[mix]", "-ar", "48000", str(pre)]
    )
    _loudnorm_two_pass(pre, out, sb.meta.loudness_lufs, sb.meta.true_peak_db)
    pre.unlink(missing_ok=True)
    return out


# ----------------------------------------------------------------- export ---


def _mux(picture: Path, mix: Path, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.stem + ".part.mp4")
    media.run(
        [
            "-i",
            str(picture),
            "-i",
            str(mix),
            "-map",
            "0:v",
            "-map",
            "1:a",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(tmp),
        ]
    )
    shutil.move(tmp, out)


def radio_cut(sb: Storyboard, timeline: dict[str, Any]) -> Path:
    """Narration over temp music on black, with English subtitles: the first audience test."""
    total = timeline["total"]
    mix = render_mix(sb, timeline, music=None)
    subs = config.OUTPUTS / "subs" / "16x9.ass"
    vf = (
        f"subtitles=filename={subs.relative_to(config.ROOT)}:fontsdir=fonts"
        if subs.exists()
        else "null"
    )
    pic = TMP / f"radio_black_{hash_obj([total, hash_file(subs) if subs.exists() else None])}.mp4"
    if not pic.exists():
        media.run(
            [
                "-f",
                "lavfi",
                "-i",
                f"color=c=black:s=1920x1080:r=24:d={total:.3f}",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "28",
                str(pic),
            ]
        )
    out = FINAL / "radio_cut.mp4"
    _mux(pic, mix, out)
    print(f"[assemble] radio cut -> {out.relative_to(config.ROOT)} ({total:.1f}s)")
    return out


def film(
    sb: Storyboard,
    timeline: dict[str, Any],
    music: Path | None,
    ratios: list[str],
    allow_draft: bool,
) -> list[Path]:
    mix = render_mix(sb, timeline, music)
    outs = []
    for ratio in ratios:
        pic, kinds = render_picture(sb, timeline, ratio, allow_draft)
        out = FINAL / f"a_little_further_{ratio}.mp4"
        _mux(pic, mix, out)
        summary = {k: list(kinds.values()).count(k) for k in set(kinds.values())}
        (out.with_suffix(".json")).write_text(
            json.dumps(
                {
                    "ratio": ratio,
                    "total_s": timeline["total"],
                    "segments": kinds,
                    "summary": summary,
                    "music": str(music.relative_to(config.ROOT)) if music else "placeholder",
                    "picture": pic.name,
                    "mix": mix.name,
                    "edit": EDIT,
                },
                indent=2,
            )
            + "\n"
        )
        print(f"[assemble] {ratio} -> {out.relative_to(config.ROOT)} {summary}")
        outs.append(out)
    return outs
