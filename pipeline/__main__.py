"""CLI: python -m pipeline <command>.  `make film` runs `film`."""

from __future__ import annotations

import json
from typing import Annotated

import typer

from pipeline.core import config
from pipeline.core.calls import CTX
from pipeline.core.config import MissingCredentials
from pipeline.models import Storyboard
from pipeline.stages import common

app = typer.Typer(add_completion=False, no_args_is_help=True, help=__doc__)


@app.callback()
def main(
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="Explain what would be generated vs reused")
    ] = False,
    force: Annotated[bool, typer.Option("--force", help="Regenerate even if cached")] = False,
    allow_draft: Annotated[
        bool, typer.Option("--allow-draft", help="Use unapproved refs/keyframes")
    ] = False,
    shot: Annotated[
        list[str] | None, typer.Option("--shot", help="Limit to shot id(s), repeatable")
    ] = None,
) -> None:
    CTX.dry_run, CTX.force, CTX.allow_draft = dry_run, force, allow_draft
    CTX.shots = set(shot) if shot else None


def _load() -> Storyboard:
    try:
        return common.load()
    except common.StoryboardError as exc:
        typer.secho(str(exc), fg="red", err=True)
        raise typer.Exit(2) from exc


def _print_plan() -> None:
    if not CTX.dry_run:
        return
    gen = [p for p in CTX.plan if p["action"] != "reuse"]
    typer.echo(f"\nDRY RUN: {len(gen)} asset(s) to generate, {len(CTX.plan) - len(gen)} reused")
    for p in CTX.plan:
        mark = "REUSE   " if p["action"] == "reuse" else "GENERATE"
        why = f"  changed: {', '.join(p['changed'])}" if p.get("changed") else ""
        typer.echo(f"  {mark} {p['stage']:<10} {p['item']:<16} {p['key']}{why}")
    if gen:
        typer.echo("  RENDER   assemble   (inputs changed; deterministic FFmpeg, no model calls)")


@app.command()
def validate() -> None:
    """Validate storyboard.json against the contract (also runs at the start of every stage)."""
    sb = _load()
    total = sum(s.min_duration_s for s in sb.shots) + sb.end_card.duration_s
    typer.secho(f"storyboard OK: {len(sb.shots)} shots, planned >= {total:.1f}s", fg="green")


@app.command()
def schema() -> None:
    """Regenerate schema/storyboard.schema.json from the Pydantic models."""
    config.SCHEMA.parent.mkdir(exist_ok=True)
    config.SCHEMA.write_text(
        json.dumps(Storyboard.model_json_schema(), indent=2, ensure_ascii=False) + "\n"
    )
    typer.echo(f"wrote {config.SCHEMA.relative_to(config.ROOT)}")


@app.command()
def translate(
    apply: Annotated[
        bool, typer.Option("--apply", help="Write the draft into narration.text")
    ] = False,
    language: Annotated[
        str | None, typer.Option(help="Target language code (default meta.language)")
    ] = None,
) -> None:
    """Draft the narration translation from text_en with Gemini (native-speaker review required)."""
    from pipeline.stages import script

    sb = _load()
    tr = script.draft(sb, language)
    for sid, text in tr.items():
        typer.echo(f"{sid}: {text}")
    if apply and tr and not CTX.dry_run:
        typer.echo(f"applied {script.apply(tr)} line(s) to storyboard.json")
    _print_plan()


@app.command()
def audition(
    text: Annotated[str, typer.Option(help="Line to read (default: s01 narration)")] = "",
    voice: Annotated[list[str] | None, typer.Option(help="provider:voice, repeatable")] = None,
) -> None:
    """Experiment 1: render one line in several voices, plus blind-labelled copies (A, B, C...)."""
    import shutil

    from pipeline.core.calls import call_model
    from pipeline.stages import narration as nar

    sb = _load()
    line = text or sb.shots[0].narration.text
    voices = voice or [
        "addis:am-loza",
        "addis:am-sara",
        "addis:am-hamen",
        "addis:am-melat",
        "gemini:Kore",
    ]
    blind_dir = config.OUTPUTS / "audition" / "blind"
    blind_dir.mkdir(parents=True, exist_ok=True)
    key_rows = []
    for i, spec in enumerate(voices):
        pname, vname = spec.split(":", 1)
        prov = nar.provider_for(pname)
        inputs = {
            "text": line,
            "language": sb.meta.language,
            "voice": vname,
            "speed": 1.0,
            "style": None,
        }
        try:
            out = call_model(
                stage="audition",
                item=f"{pname}_{vname}",
                provider=prov.name,
                model=prov.model,
                inputs=inputs,
                ext="wav",
                run=lambda tmp, prov=prov, vname=vname: prov.synthesize(
                    line, tmp, voice=vname, language=sb.meta.language, speed=1.0, style=None
                ),
            )
        except Exception as exc:  # noqa: BLE001 - one unavailable voice must not sink the test
            key_rows.append(f"{chr(ord('A') + i)} = {spec} FAILED: {str(exc)[:100]}")
            continue
        if out:
            label = chr(ord("A") + i)
            shutil.copyfile(out, blind_dir / f"voice_{label}.wav")
            key_rows.append(f"{label} = {spec} ({out.relative_to(config.ROOT)})")
    (blind_dir / "KEY_do_not_share.txt").write_text("\n".join(key_rows) + "\n")
    typer.echo(f"blind files in {blind_dir.relative_to(config.ROOT)}; key in KEY_do_not_share.txt")


@app.command()
def narration() -> None:
    """Generate one narration clip per shot and the measured timeline."""
    from pipeline.stages import narration as st

    st.run(_load())
    _print_plan()


@app.command()
def subtitles() -> None:
    """Write English subtitles (ASS per ratio + SRT) from the timeline."""
    from pipeline.stages import narration
    from pipeline.stages import subtitles as st

    sb = _load()
    st.run(sb, narration.build_timeline(sb))


@app.command()
def refs(
    candidates: Annotated[int, typer.Option(help="Seeds to explore per subject")] = 1,
    only: Annotated[
        list[str] | None, typer.Option(help="Only these character/location ids")
    ] = None,
) -> None:
    """Generate character/location reference images (before any keyframe)."""
    from pipeline.stages import refs as st

    st.run(_load(), candidates=candidates, only=set(only) if only else None)
    _print_plan()


@app.command()
def keyframes(
    candidates: Annotated[int, typer.Option(help="Seeds to explore per shot")] = 1,
) -> None:
    """Generate one keyframe per shot, conditioned on approved references."""
    from pipeline.stages import keyframes as st

    st.run(_load(), candidates=candidates)
    _print_plan()


@app.command("video-submit")
def video_submit(
    limit: Annotated[int | None, typer.Option(help="Max clips to submit")] = None,
) -> None:
    """Bundle approved keyframes and push the Wan 2.2 job to Kaggle."""
    from pipeline.stages import video as st

    st.submit(_load(), limit=limit)
    _print_plan()


@app.command("video-status")
def video_status() -> None:
    from pipeline.stages import video as st

    typer.echo(st.status())


@app.command("video-fetch")
def video_fetch() -> None:
    """Download finished clips from Kaggle and register them in the cache."""
    from pipeline.stages import video as st

    st.fetch()


@app.command()
def music() -> None:
    """Generate the score candidates listed in storyboard.music.seeds."""
    from pipeline.stages import music as st

    st.run(_load())
    _print_plan()


@app.command()
def radio() -> None:
    """Radio cut: narration + temp music on black with subtitles (first audience test)."""
    from pipeline.stages import assemble
    from pipeline.stages import narration as nar
    from pipeline.stages import subtitles as subs

    sb = _load()
    nar.run(sb)
    if CTX.dry_run:
        return _print_plan()
    tl = nar.build_timeline(sb)
    subs.run(sb, tl)
    assemble.radio_cut(sb, tl)


@app.command()
def assemble(
    ratio: Annotated[list[str] | None, typer.Option(help="9x16 and/or 16x9")] = None,
) -> None:
    """Assemble the film from whatever is cached (Wan clip > Ken Burns > placeholder)."""
    from pipeline.stages import assemble as st
    from pipeline.stages import music as mus
    from pipeline.stages import narration as nar
    from pipeline.stages import subtitles as subs

    sb = _load()
    tl = nar.build_timeline(sb)
    subs.run(sb, tl)
    st.film(sb, tl, mus.chosen_path(sb), ratio or ["9x16", "16x9"], CTX.allow_draft)


@app.command()
def film() -> None:
    """The whole pipeline, end to end. Cached assets are reused; missing keys degrade gracefully."""
    from pipeline.stages import assemble as asm
    from pipeline.stages import keyframes as kf
    from pipeline.stages import music as mus
    from pipeline.stages import narration as nar
    from pipeline.stages import refs as rf
    from pipeline.stages import subtitles as subs

    sb = _load()
    skipped = []
    for name, fn in (
        ("narration", lambda: nar.run(sb)),
        ("refs", lambda: rf.run(sb)),
        ("keyframes", lambda: kf.run(sb)),
        ("music", lambda: mus.run(sb)),
    ):
        try:
            fn()
        except (MissingCredentials, kf.RefsNotApproved) as exc:
            skipped.append(name)
            typer.secho(f"[film] {name}: skipped ({exc})", fg="yellow")
    if CTX.dry_run:
        return _print_plan()
    tl = nar.build_timeline(sb)
    subs.run(sb, tl)
    asm.film(sb, tl, mus.chosen_path(sb), ["9x16", "16x9"], CTX.allow_draft)
    if skipped:
        typer.secho(f"[film] finished with fallbacks; skipped stages: {skipped}", fg="yellow")


@app.command()
def approve(
    kind: Annotated[str, typer.Argument(help="refs | keyframes")],
    ids: Annotated[list[str], typer.Argument(help="character/location ids or shot ids")],
) -> None:
    """Record approval: stores the current cache key of each asset in storyboard.json."""
    from pipeline.core import cache
    from pipeline.core.calls import compute_key
    from pipeline.providers.cloudflare import CloudflareImage
    from pipeline.stages import keyframes as kf
    from pipeline.stages import refs as rf

    sb, raw = _load(), common.load_raw()
    prov = CloudflareImage()
    for item in ids:
        if kind == "refs":
            subj = next((s for s in rf.subjects(sb) if s[0] == item), None)
            if not subj:
                raise typer.BadParameter(f"unknown ref id {item}")
            key = compute_key(rf.STAGE, prov.name, prov.model, rf.inputs_for(sb, subj[1], subj[2]))
            stage = rf.STAGE
            target = next((c for c in raw["characters"] if c["id"] == item), None) or next(
                loc for loc in raw["locations"] if loc["id"] == item
            )
            target["ref"]["approved_key"] = key
        elif kind == "keyframes":
            inputs, _ = kf.inputs_for(sb, sb.shot(item))
            key = compute_key(kf.STAGE, prov.name, prov.model, inputs)
            stage = kf.STAGE
            next(s for s in raw["shots"] if s["id"] == item)["keyframe"]["approved_key"] = key
        else:
            raise typer.BadParameter("kind must be refs or keyframes")
        if not cache.lookup(stage, item, key, "png"):
            raise typer.BadParameter(
                f"{item}: no generated asset for the current inputs; generate first"
            )
        typer.echo(f"approved {kind} {item} -> {key}")
    common.save_raw(raw)


@app.command("choose-music")
def choose_music(
    seed: int, why: Annotated[str, typer.Option(help="Why this candidate won")]
) -> None:
    """Pick the score candidate used in the film."""
    raw = common.load_raw()
    raw["music"]["chosen_seed"], raw["music"]["why"] = seed, why
    common.save_raw(raw)
    _load()
    typer.echo(f"music: chose seed {seed}")


@app.command()
def smoke() -> None:
    """Call each provider once with a tiny input and log latency to runs.jsonl."""
    from pipeline.tools import smoke as st

    st.run()


@app.command()
def costs() -> None:
    """Summarise runs.jsonl into per-stage latency / GPU time / list-price cost (for COSTS.md)."""
    from pipeline.tools import costs_report

    typer.echo(costs_report.markdown())


@app.command()
def audit() -> None:
    """Check provenance: every asset has a sidecar and a runs.jsonl entry."""
    from pipeline.tools import audit as st

    raise typer.Exit(st.run())


if __name__ == "__main__":
    app()
