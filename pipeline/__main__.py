from __future__ import annotations

import json
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from . import (
    avisos,
    canvas,
    config,
    integrate,
    migrate,
    note_validate,
    notes_clean,
    prompt_builder,
    runner,
    state,
    units,
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


def _units_json(course: str):
    return config.WORK / course / "units.json"


def _temas_base(course: str):
    """Dir holding `temas/`: work/<c> once the course moved to unit documents, else vault/<c>."""
    return config.WORK / course if _units_json(course).exists() else config.VAULT / course


def _full_name(course: str) -> str:
    s = _settings()
    if course not in s.courses:
        raise typer.BadParameter(f"unknown course '{course}' (known: {', '.join(s.courses)})")
    return s.courses[course].full_name


def _class_stems(course: str) -> set[str]:
    return {p.stem for p in (config.VAULT / course / "clases").glob("*.md")}


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
    temas = sorted((slug, title) for title, slug in integrate.slug_titles(_temas_base(course)).items())
    p = prompt_builder.build_analysis_prompt(meta, d["work"] / "transcript.md", d["work"] / "frames.json",
                                             d["note"], d["work"] / "temas-candidatos.json", meta["img_rel"], temas)
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
    """Validate the class note (frontmatter, sections, images, wikilinks)."""
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
        extra |= {p.stem for p in (config.WORK / course / "temas").glob("*.md")}  # archived temas still resolve
        errs = note_validate.validate(d["note"], config.VAULT, extra)
        state.mark(d["state"], "validate", "ok" if not errs else "blocked", errors=errs)
        con.print(f"{cid}: {'OK' if not errs else errs}")


@app.command("integrate")
def integrate_cmd(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
                  force: bool = False,
                  assign: Annotated[list[str] | None, typer.Option(help="TEMA=UNIT_SLUG (repetible)")] = None):
    """Merge temas-candidatos into the temas dir and regenerate MOC / avisos / calendario."""
    s = _settings()
    full_name = _full_name(course)
    vc = config.VAULT / course
    unit_mode = _units_json(course).exists()
    base = _temas_base(course)
    for cid in _classes(course, "integrate", class_id, force):
        d = config.class_dirs(course, cid)
        cands_path = d["work"] / "temas-candidatos.json"
        if not cands_path.exists():
            state.mark(d["state"], "integrate", "blocked", error="sin temas-candidatos.json")
            continue
        counts = {"created": 0, "updated": 0, "unchanged": 0}
        cands = ch.load_json(cands_path)
        index = integrate.title_index(base, cands)
        for cand in cands:
            counts[integrate.upsert_tema(base, course, cand, cid, index)] += 1
        state.mark(d["state"], "integrate", "ok", **counts)
        con.print(f"{cid}: {counts}")
    if (base / "temas").exists():
        n = integrate.relink_dangling(base, _class_stems(course) if unit_mode else None)
        con.print(f"links de temas re-apuntados: {n}") if n else None
    if unit_mode:
        uj = _units_json(course)
        us = units.load_units(uj)
        by_slug = {u.slug: u for u in us}
        for pair in assign or []:
            tema, _, unit_slug = pair.partition("=")
            if unit_slug.strip() not in by_slug:
                raise typer.BadParameter(f"unidad inexistente: {unit_slug} (hay: {', '.join(by_slug)})")
            by_slug[unit_slug.strip()].add_tema(tema.strip())
            con.print(f"{tema.strip()} -> {unit_slug.strip()}")
        if assign:
            units.save_units(uj, us)
        placed = {t for u in us for t in u.temas}
        new = sorted(p.stem for p in (base / "temas").glob("*.md") if p.stem not in placed)
        if new:
            con.print(f"temas NUEVOS sin unidad ({len(new)}): {', '.join(new)} -> asignar con --assign TEMA=UNIT_SLUG")
        units.regen_moc_units(vc, course, full_name, us)
    else:
        integrate.regen_moc(vc, course, full_name)
    integrate.regen_avisos(vc, course)
    integrate.regen_calendario(config.VAULT, list(s.courses))


@app.command("merge-temas")
def merge_temas(pairs: Annotated[list[str], typer.Argument(help="duplicado=canonico")], course: str = typer.Option(...)):
    """Fold duplicate topics into their canonical slug and rewrite every wikilink (then run integrate)."""
    vc = config.VAULT / course
    unit_mode = _units_json(course).exists()
    base = _temas_base(course)
    roots = [base / "temas", vc / "clases"] if unit_mode else None
    for pair in pairs:
        src, _, dst = pair.partition("=")
        n = integrate.merge_tema(base, src.strip(), dst.strip(), config.WORK / course / "_merged-temas",
                                 config.WORK / course, roots)
        if unit_mode:
            units.rename_tema(config.WORK / course, src.strip(), dst.strip())
        con.print(f"{src} -> {dst}: {n} archivos reescritos")
    if unit_mode:
        units.regen_moc_units(vc, course, _full_name(course), units.load_units(_units_json(course)))
    else:
        integrate.regen_moc(vc, course, _full_name(course))


@app.command("canvas")
def canvas_cmd(course: str = typer.Option(...)):
    """Build vault/<course>/MOC-<course>.canvas (course -> units -> sections, or the old MOC outline)."""
    out = _write_canvas(course)
    con.print(f"{ch.relpath(out)}: {len(json.loads(out.read_text(encoding='utf-8'))['nodes'])} nodos")


def _write_canvas(course: str):
    vc = config.VAULT / course
    if _units_json(course).exists():
        us = units.load_units(_units_json(course))
        h2s = {u.slug: units.unit_h2s(units.doc_path(vc, u)) for u in us}
        data = canvas.to_canvas_units(_full_name(course), course, us, h2s)
    else:
        moc = vc / f"MOC-{course}.md"
        names = {p.stem: p.relative_to(config.VAULT).as_posix() for p in config.VAULT.rglob("*.md")}
        data = canvas.to_canvas(_full_name(course), canvas.outline(moc.read_text(encoding="utf-8")), names.get)
    out = vc / f"MOC-{course}.canvas"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return out


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
        dump = s.drive_root / "_clases-dump" / course / cid
        if d["raw"].exists():
            sync_mod.move_raw(d["raw"], s.drive_root / "_clases-dump", course, cid)
        sync_mod.repoint_video(d["note"], dump / "video.mp4")
        state.mark(d["state"], "sync", "ok")
        con.print(f"{cid}: crudo movido a _clases-dump")
    sync_mod.mirror_vault(config.VAULT / course, s.drive_root / c.drive_folder)
    con.print(f"vault/{course} -> {c.drive_folder}/notas/")
    for p in sync_mod.copy_root_notes(config.VAULT, s.drive_root):
        con.print(f"{p.name} -> DRIVE_ROOT/")


@app.command("strip-timestamps")
def strip_timestamps(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class")):
    """Remove [hh:mm:ss] timestamps from the class notes (frontmatter and code blocks untouched)."""
    clases = config.VAULT / course / "clases"
    notes = [config.class_dirs(course, class_id)["note"]] if class_id else sorted(clases.glob("*.md"))
    total = 0
    for note in notes:
        if not note.exists():
            con.print(f"{note.stem}: nota inexistente")
            continue
        n = notes_clean.strip_file(note)
        total += n
        con.print(f"{note.stem}: {n}") if n else None
    con.print(f"timestamps removidos: {total} en {len(notes)} notas")


@app.command("rename-notes")
def rename_notes(course: str = typer.Option(...)):
    """Rename class notes to `<curso>-<class_id>.md` and rewrite the wikilinks to them (idempotent)."""
    _full_name(course)
    r = migrate.rename_notes(course)
    con.print(f"{course}: notas renombradas {r.renamed}; links reescritos {r.links} en {r.files} archivos")


@app.command("units-init")
def units_init(course: str = typer.Option(...), force: bool = False):
    """Derive work/<c>/units.json from the MOC '## Mapa' outline and move temas/ out of the vault into work/<c>/."""
    uj = _units_json(course)
    if uj.exists() and not force:
        con.print(f"{ch.relpath(uj)} ya existe (usar --force para regenerarlo desde el MOC)")
        return
    vc, wc = config.VAULT / course, config.WORK / course
    moc = vc / f"MOC-{course}.md"
    us = units.parse_outline(moc.read_text(encoding="utf-8")) if moc.exists() else []
    if not us:
        con.print(f"{ch.relpath(moc)}: sin outline '## Mapa' con unidades")
        raise typer.Exit(1)
    moved = units.archive_temas(vc, wc)
    orphans = units.assign_orphans(us, wc)
    units.save_units(uj, us)
    con.print(f"{ch.relpath(uj)}: {len(us)} unidades; temas archivados en {ch.relpath(wc / 'temas')}: {moved}")
    for u in us:
        con.print(f"  {u.slug}: {len(u.temas)} temas en {len(u.groups)} grupos")
    for tema, unit_slug in orphans:
        con.print(f"  huérfano {tema} -> {unit_slug}")
    con.print(f"huérfanos asignados: {len(orphans)}")


@app.command("unit-prompt")
def unit_prompt(course: str = typer.Option(...), unit: str | None = typer.Option(None, "--unit"),
                update: str | None = typer.Option(None, "--update", help="TEMA1,TEMA2: modo actualización")):
    """Write work/<c>/units/<slug>.prompt.md for the redactor-unidad agent (one unit or all)."""
    uj = _units_json(course)
    if not uj.exists():
        raise typer.BadParameter(f"falta {ch.relpath(uj)} (correr units-init)")
    us = units.load_units(uj)
    upd = [t.strip() for t in update.split(",") if t.strip()] if update else None
    sel = [u for u in us if u.slug == unit] if unit else us
    if unit and not sel:
        raise typer.BadParameter(f"unidad inexistente: {unit} (hay: {', '.join(u.slug for u in us)})")
    vc, wc = config.VAULT / course, config.WORK / course
    full_name = _full_name(course)
    for u in sel:
        mine = [t for t in upd if t in u.temas] if upd else None
        if upd and not mine:
            if unit:
                con.print(f"{u.slug}: ninguno de {', '.join(upd)} está en la unidad (asignar con integrate --assign)")
            continue
        p = units.build_unit_prompt(course, full_name, u, us, vc, wc, mine)
        out = wc / "units" / f"{u.slug}.prompt.md"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(p, encoding="utf-8")
        con.print(f"{ch.relpath(out)}: {len(p)} chars")


@app.command("units-finish")
def units_finish(course: str = typer.Option(...)):
    """Check unit docs + maps, relink class notes to unit sections, regenerate MOC / canvas / avisos / calendario."""
    s = _settings()
    uj = _units_json(course)
    if not uj.exists():
        raise typer.BadParameter(f"falta {ch.relpath(uj)} (correr units-init)")
    us = units.load_units(uj)
    vc, wc = config.VAULT / course, config.WORK / course
    errs = [e for u in us for e in units.check_map(units.doc_path(vc, u), units.map_path(wc, u), u)]
    if errs:
        for e in errs:
            con.print(e)
        con.print(f"{len(errs)} errores: no se tocó nada")
        raise typer.Exit(1)
    maps: dict[str, tuple[str, str]] = {}
    for u in us:
        for tema, heading in units.load_map(units.map_path(wc, u)).items():
            maps[tema] = (u.slug, str(heading).strip())
    titles = {t: units.tema_info(wc, t)["titulo"] for t in maps}
    plain = 0
    for note in sorted((vc / "clases").glob("*.md")):
        new, k = notes_clean.plain_headings(note.read_text(encoding="utf-8"))
        if k:
            note.write_text(new, encoding="utf-8")
            plain += k
    n = units.relink_classes(vc, maps, titles)
    full_name = _full_name(course)
    units.regen_moc_units(vc, course, full_name, us)
    _write_canvas(course)
    integrate.regen_avisos(vc, course)
    integrate.regen_calendario(config.VAULT, list(s.courses))
    units.regen_root_moc(config.VAULT, {slug: c.full_name for slug, c in s.courses.items()})
    con.print(f"links de clases re-apuntados a unidades: {n}; MOC, canvas, avisos, calendario y 00-MOC regenerados")
    files = sorted(vc.rglob("*.md")) + sorted(config.VAULT.glob("*.md"))
    fixed = units.fix_anchors(config.VAULT, files)
    con.print(f"encabezados de clase normalizados: {plain}; anclas corregidas: {fixed}")
    problems = units.check_links(config.VAULT, files)
    con.print(f"links con problemas: {len(problems)}")
    for e in problems[:20]:
        con.print(f"  {e}")


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
        for sub in ("clases/img", "unidades"):
            (config.VAULT / slug / sub).mkdir(parents=True, exist_ok=True)
    moc = config.VAULT / "00-MOC-2026.md"
    if not moc.exists():
        moc.write_text("# 2026 — cursos\n\n" + "".join(f"- [[MOC-{slug}]] — {c.full_name}\n" for slug, c in s.courses.items()),
                       encoding="utf-8")
    con.print(f"vault listo en {config.VAULT} (abrir esa carpeta como bóveda en Obsidian)")


if __name__ == "__main__":
    app()
