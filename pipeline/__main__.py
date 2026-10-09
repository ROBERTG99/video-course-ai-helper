from __future__ import annotations

import json

import typer
from rich.console import Console
from rich.table import Table

from . import (
    avisos,
    canvas,
    config,
    integrate,
    note_validate,
    prompt_builder,
    runner,
    state,
    vtt,
)
from . import cli_helpers as ch
from . import fetch as fetch_mod
from . import frames as frames_mod
from . import sync as sync_mod

app = typer.Typer(help="Video Course AI Helper pipeline", no_args_is_help=True)
con = Console(width=200)


def _settings():
    return config.load_settings()


def _classes(course: str, stage: str, class_id: str | None, force: bool) -> list[str]:
    if class_id:
        return [class_id]
    return ch.pending_classes(course, stage, force)


@app.command("list-showcase")
def list_showcase(course: str = typer.Option(...)):
    """List the showcase videos with the class ids they would get."""
    from .naming import assign_ids
    from .vimeo import VimeoShowcase

    c = config.course(_settings(), course)
    vids = VimeoShowcase(c.showcase_id, c.password).list_videos()
    ids = assign_ids(vids)
    for v in vids:
        con.print(f"{ids[v.video_id]}  {v.video_id}  {v.duration // 60} min  {v.title}")


@app.command()
def fetch(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
          subs_only: bool = False, force: bool = False):
    """Download captions (+ video unless --subs-only) for every class not fetched yet."""
    c = config.course(_settings(), course)
    for r in fetch_mod.fetch_course(c, subs_only=subs_only, only_class=class_id, force=force):
        con.print(r)


@app.command()
def transcript(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
               force: bool = False):
    """Convert the Vimeo VTT into work/<course>/<class>/transcript.md."""
    s = _settings()
    for cid in _classes(course, "transcript", class_id, force):
        d = config.class_dirs(course, cid)
        v = state.load(d["state"])["stages"].get("fetch", {}).get("vtt")
        if not v:
            state.mark(d["state"], "transcript", "blocked", error="sin VTT")
            continue
        n = vtt.convert(ch.resolve_path(v), d["work"] / "transcript.md", f"{course} · {cid}",
                        float(s.transcript["paragraph_seconds"]), config.glossary_path(course))
        state.mark(d["state"], "transcript", "ok", cues=n)
        con.print(f"{cid}: {n} cues -> {ch.relpath(d['work'] / 'transcript.md')}")


@app.command()
def frames(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
           force: bool = False):
    """Sample, dedupe and OCR key frames from the class video."""
    s = _settings()
    for cid in _classes(course, "frames", class_id, force):
        d = config.class_dirs(course, cid)
        video = state.load(d["state"])["stages"].get("fetch", {}).get("video")
        if not video:
            state.mark(d["state"], "frames", "blocked", error="sin video (corré fetch sin --subs-only)")
            continue
        try:
            segs = frames_mod.process(ch.resolve_path(video), d["work"], d["img"], cid, s.frames)
        except Exception as e:  # noqa: BLE001 - ffmpeg/tesseract failures are reported, not hidden
            state.mark(d["state"], "frames", "blocked", error=str(e)[:500])
            continue
        kept = sum(1 for x in segs if x.keep)
        state.mark(d["state"], "frames", "ok", segments=len(segs), kept=kept)
        con.print(f"{cid}: {len(segs)} segments, {kept} kept -> {ch.relpath(d['img'])}")


@app.command()
def prompt(course: str = typer.Option(...), class_id: str = typer.Option(..., "--class")):
    """Build work/<course>/<class>/analysis-prompt.md and avisos-excerpts.md (no LLM call)."""
    s = _settings()
    c = config.course(s, course)
    d = config.class_dirs(course, class_id)
    meta = ch.meta_for(c, class_id)
    p = prompt_builder.build_analysis_prompt(meta, d["work"] / "transcript.md", d["work"] / "frames.json",
                                             d["note"], d["work"] / "temas-candidatos.json", meta["img_rel"])
    (d["work"] / "analysis-prompt.md").write_text(p, encoding="utf-8")
    hits = avisos.excerpts(avisos.read_transcript(d["work"] / "transcript.md"), s.avisos_keywords)
    (d["work"] / "avisos-excerpts.md").write_text(avisos.to_markdown(hits), encoding="utf-8")
    con.print(f"{class_id}: prompt {len(p)} chars, {len(hits)} fragmentos de avisos -> {ch.relpath(d['work'])}")


@app.command("avisos-prompt")
def avisos_prompt(course: str = typer.Option(...), class_id: str = typer.Option(..., "--class")):
    """Build work/<course>/<class>/avisos-prompt.md for the verificador-avisos agent (needs the note + excerpts)."""
    c = config.course(_settings(), course)
    d = config.class_dirs(course, class_id)
    p = prompt_builder.build_avisos_prompt(ch.meta_for(c, class_id), d["work"] / "avisos-excerpts.md", d["note"],
                                           d["work"] / "avisos-review.md")
    (d["work"] / "avisos-prompt.md").write_text(p, encoding="utf-8")
    con.print(f"Prompt listo: {ch.relpath(d['work'] / 'avisos-prompt.md')} -> despachar agente verificador-avisos (opus)")


@app.command()
def analyze(course: str = typer.Option(...), class_id: str = typer.Option(..., "--class"),
            runner_name: str = typer.Option("agent", "--runner"), budget: float = 3.0, force: bool = False):
    """runner=agent: builds the prompt (or marks ok once the agent delivered). runner=claude-p: runs headless."""
    d = config.class_dirs(course, class_id)
    cands = d["work"] / "temas-candidatos.json"
    if state.is_done(d["state"], "analyze") and not force:
        con.print(f"{class_id}: analyze ya ok (usar --force)")
        return
    if runner_name == "agent" and not force and d["note"].exists() and cands.exists():
        state.mark(d["state"], "analyze", "ok", runner="agent")
        con.print(f"{class_id}: nota y temas-candidatos presentes -> analyze ok (agent)")
        return
    prompt(course, class_id)
    if runner_name == "agent":
        con.print(f"Prompt listo: {ch.relpath(d['work'] / 'analysis-prompt.md')} -> despachar agente analista-clase (sonnet)")
        return
    try:
        r = runner.run_claude(d["work"] / "analysis-prompt.md", "sonnet", budget)
    except Exception as e:
        state.mark(d["state"], "analyze", "blocked", error=str(e)[:500])
        raise typer.Exit(1) from e
    if not d["note"].exists():
        state.mark(d["state"], "analyze", "blocked", error="claude -p terminó sin escribir la nota", **r)
        raise typer.Exit(1)
    state.mark(d["state"], "analyze", "ok", runner="claude-p", **r)
    con.print(f"{class_id}: nota escrita, costo {r['cost_usd']}")


@app.command()
def validate(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
             force: bool = False):
    """Validate the class note (frontmatter, sections, images, wikilinks, timestamps)."""
    for cid in _classes(course, "validate", class_id, force):
        d = config.class_dirs(course, cid)
        if not d["note"].exists():
            state.mark(d["state"], "validate", "blocked", errors=["nota inexistente"])
            con.print(f"{cid}: nota inexistente")
            continue
        extra: set[str] = set()
        cands_path = d["work"] / "temas-candidatos.json"
        if cands_path.exists():  # topics are created later by `integrate`: their links are not broken
            extra = {c.get("slug") or integrate.slugify(c["titulo"]) for c in ch.load_json(cands_path)}
        errs = note_validate.validate(d["note"], config.VAULT, extra)
        state.mark(d["state"], "validate", "ok" if not errs else "blocked", errors=errs)
        con.print(f"{cid}: {'OK' if not errs else errs}")


@app.command("integrate")
def integrate_cmd(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
                  force: bool = False):
    """Merge temas-candidatos into the vault and regenerate MOC / avisos / calendario."""
    s = _settings()
    c = config.course(s, course)
    vc = config.VAULT / course
    for cid in _classes(course, "integrate", class_id, force):
        d = config.class_dirs(course, cid)
        cands_path = d["work"] / "temas-candidatos.json"
        if not cands_path.exists():
            state.mark(d["state"], "integrate", "blocked", error="sin temas-candidatos.json")
            continue
        counts = {"created": 0, "updated": 0, "unchanged": 0}
        for cand in ch.load_json(cands_path):
            counts[integrate.upsert_tema(vc, course, cand, cid)] += 1
        state.mark(d["state"], "integrate", "ok", **counts)
        con.print(f"{cid}: {counts}")
    integrate.regen_moc(vc, course, c.full_name)
    integrate.regen_avisos(vc, course)
    integrate.regen_calendario(config.VAULT, list(s.courses))


@app.command("canvas")
def canvas_cmd(course: str = typer.Option(...)):
    """Build vault/<course>/MOC-<course>.canvas from the MOC outline."""
    vc = config.VAULT / course
    moc = vc / f"MOC-{course}.md"
    names = {p.stem: p.relative_to(config.VAULT).as_posix() for p in config.VAULT.rglob("*.md")}
    data = canvas.to_canvas(config.course(_settings(), course).full_name,
                            canvas.outline(moc.read_text(encoding="utf-8")), names.get)
    out = vc / f"MOC-{course}.canvas"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    con.print(f"{ch.relpath(out)}: {len(data['nodes'])} nodos")


@app.command("sync")
def sync_cmd(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
             force: bool = False):
    """Move raw media to the Drive dump and mirror the vault to the course folder."""
    s = _settings()
    c = config.course(s, course)
    if str(s.drive_root) in ("", ".") or not s.drive_root.exists():
        raise typer.BadParameter(f"DRIVE_ROOT no definido o inexistente: {s.drive_root}")
    for cid in _classes(course, "sync", class_id, force):
        d = config.class_dirs(course, cid)
        if d["raw"].exists():
            sync_mod.move_raw(d["raw"], s.drive_root / "_clases-dump", course, cid)
        state.mark(d["state"], "sync", "ok")
        con.print(f"{cid}: crudo movido a _clases-dump")
    sync_mod.mirror_vault(config.VAULT / course, s.drive_root / c.drive_folder)
    con.print(f"vault/{course} -> {c.drive_folder}/notas/")


@app.command()
def status(course: str | None = typer.Option(None)):
    """Per-class stage table (ok / blocked / ·)."""
    s = _settings()
    for slug in ([course] if course else list(s.courses)):
        paths = sorted((config.STATE / slug).glob("*.json"))
        if not paths:
            continue
        t = Table(title=slug)
        t.add_column("clase", no_wrap=True)
        for st in state.STAGES:
            t.add_column(st, no_wrap=True)
        for p in paths:
            data = state.load(p)
            row = [data.get("class_id") or p.stem]
            for st in state.STAGES:
                row.append(data.get("stages", {}).get(st, {}).get("status", "·"))
            t.add_row(*row)
        con.print(t)


@app.command("init-vault")
def init_vault():
    """Create the vault skeleton (open vault/ as an Obsidian vault)."""
    s = _settings()
    for slug in s.courses:
        for sub in ("clases/img", "temas"):
            (config.VAULT / slug / sub).mkdir(parents=True, exist_ok=True)
    moc = config.VAULT / "00-MOC-2026.md"
    if not moc.exists():
        moc.write_text("# 2026 — cursos\n\n" + "".join(f"- [[MOC-{slug}]] — {c.full_name}\n" for slug, c in s.courses.items()),
                       encoding="utf-8")
    con.print(f"vault listo en {config.VAULT} (abrir esa carpeta como bóveda en Obsidian)")


if __name__ == "__main__":
    app()
