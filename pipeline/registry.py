"""What is published vs. processed: `pending` (Vimeo showcase vs state/) and the vault-level `clases-registro.md`."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from . import config, integrate, state, units

REGISTRY_NAME = "clases-registro.md"


def class_status(path: Path) -> str | None:
    """None when the 7 stages are ok; `bloqueada:<stage>: <error>` if a stage is blocked; else `incompleta:<stage>`."""
    if not path.exists():
        return "nueva"
    stages = state.load(path).get("stages", {})
    for s in state.STAGES:
        info = stages.get(s, {})
        if info.get("status") == "blocked":
            err = info.get("error") or "; ".join(map(str, info.get("errors") or [])) or "sin detalle"
            return f"bloqueada:{s}: {' '.join(str(err).split())[:200]}"
    nxt = state.next_pending(path)
    return f"incompleta:{nxt}" if nxt else None


def _row(class_id: str, video_id: str, title: str, duration: int, status: str) -> dict:
    return {"class_id": class_id, "video_id": video_id, "title": title, "duration_min": round((duration or 0) / 60),
            "status": status}


def _state_rows(course: str, skip: set[str]) -> list[dict]:
    rows: list[dict] = []
    for p in sorted((config.STATE / course).glob("*.json")):
        if p.stem in skip:
            continue
        st = class_status(p)
        if st:
            d = state.load(p)
            rows.append(_row(p.stem, str(d.get("video_id") or ""), d.get("title") or "", d.get("duration") or 0, st))
    return rows


def _online_rows(settings: config.Settings, course: str) -> list[dict]:
    from .naming import assign_ids
    from .vimeo import VimeoShowcase

    c = config.course(settings, course)
    vids = VimeoShowcase(c.showcase_id, c.password).list_videos()
    ids = assign_ids(vids)
    rows: list[dict] = []
    for v in vids:
        cid = ids[v.video_id]
        st = class_status(config.class_dirs(course, cid)["state"])
        if st:
            rows.append(_row(cid, v.video_id, v.title, v.duration, st))
    return rows + _state_rows(course, set(ids.values()))


def pending(settings: config.Settings, online: bool = True, courses: list[str] | None = None) -> dict[str, list[dict]]:
    """Per course, the classes not fully processed. Online compares the Vimeo showcase with state/; offline only
    reads state/. A network / credentials failure becomes an `error: <msg>` row (plus the state/ rows)."""
    out: dict[str, list[dict]] = {}
    for slug in courses or list(settings.courses):
        if not online:
            out[slug] = _state_rows(slug, set())
            continue
        try:
            out[slug] = _online_rows(settings, slug)
        except Exception as e:  # noqa: BLE001 - one course failing (network, password, .env) must not hide the others
            msg = " ".join(str(e).split())[:300] or type(e).__name__
            out[slug] = [_row("", "", "", 0, f"error: {msg}")] + _state_rows(slug, set())
    return out


def has_pending(pend: dict[str, list[dict]]) -> bool:
    return any(not r["status"].startswith("error:") for rows in pend.values() for r in rows)


def has_errors(pend: dict[str, list[dict]]) -> bool:
    return any(r["status"].startswith("error:") for rows in pend.values() for r in rows)


def _cell(s: str) -> str:
    return " ".join(str(s).split()).replace("|", "\\|") or "—"


def _ddmm(class_id: str) -> str:
    return f"{class_id[8:10]}/{class_id[5:7]}"


def _class_link(course: str, class_id: str) -> str:
    """`[[<curso>-<id>\\|dd/mm]]` (escaped pipe: it lives in a table) when the note exists, plain dd/mm otherwise."""
    name = config.note_name(course, class_id)
    if (config.VAULT / course / "clases" / f"{name}.md").exists():
        return f"[[{name}\\|{_ddmm(class_id)}]]"
    return _ddmm(class_id)


def class_units(course: str) -> dict[str, list[units.Unit]]:
    """class_id -> units whose map.json covers a tema of that class (via temas-candidatos.json or the tema's
    'Visto en'). Empty when the course has no units.json."""
    wc = config.WORK / course
    uj = wc / "units.json"
    if not uj.exists():
        return {}
    us = units.load_units(uj)
    tema_unit: dict[str, units.Unit] = {}
    for u in us:
        mp = units.map_path(wc, u)
        if mp.exists():
            for tema in units.load_map(mp):
                tema_unit.setdefault(tema, u)
    found: dict[str, set[str]] = {}
    for tema, u in tema_unit.items():
        for cid in units.tema_info(wc, tema)["clases"]:
            found.setdefault(cid, set()).add(u.slug)
    for cands in sorted(wc.glob("*/temas-candidatos.json")):
        try:
            data = _load_list(cands)
        except ValueError:  # includes JSONDecodeError: a broken file just contributes no units
            continue
        for c in data:
            slug = c.get("slug") or integrate.slugify(c.get("titulo", ""))
            if slug in tema_unit:
                found.setdefault(cands.parent.name, set()).add(tema_unit[slug].slug)
    order = {u.slug: u for u in us}
    return {cid: [order[s] for s in sorted(ss, key=lambda s: order[s].num)] for cid, ss in found.items()}


def _load_list(p: Path) -> list[dict]:
    data = json.loads(p.read_text(encoding="utf-8"))
    return [c for c in data if isinstance(c, dict)] if isinstance(data, list) else []


def build_registry(settings: config.Settings, pend: dict[str, list[dict]] | None = None) -> str:
    pend = pending(settings, online=False) if pend is None else pend
    out = ["# Registro de clases 2026", "", f"Actualizado: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M')}", "",
           "## Pendientes", ""]
    rows = [(slug, r) for slug, rs in pend.items() for r in rs]
    if rows:
        out += ["| curso | clase | título | estado |", "|---|---|---|---|"]
        out += [f"| {slug} | {_cell(r['class_id'])} | {_cell(r['title'])} | {_cell(r['status'])} |" for slug, r in rows]
    else:
        out.append("Nada pendiente: todas las clases publicadas están procesadas.")
    out.append("")
    for slug, c in settings.courses.items():
        new = {r["class_id"]: r for r in pend.get(slug, []) if r["status"] == "nueva"}
        ids = sorted({p.stem for p in (config.STATE / slug).glob("*.json")} | set(new))
        cu = class_units(slug)
        out += [f"## {c.full_name}", ""]
        if not ids:
            out += ["Sin clases todavía.", ""]
            continue
        out += ["| # | clase | duración (min) | estado | unidades |", "|---|---|---|---|---|"]
        for cid in ids:
            sp = config.class_dirs(slug, cid)["state"]
            if cid in new:
                dur, st = new[cid]["duration_min"], "nueva"
            else:
                dur, st = round((state.load(sp).get("duration") or 0) / 60), class_status(sp) or "✅"
            us = " ".join(f"[[{u.slug}\\|{u.num:02d}]]" for u in cu.get(cid, [])) or "—"
            num = int(cid[-2:]) if cid[-2:].isdigit() else "—"
            out.append(f"| {num} | {_class_link(slug, cid)} | {dur} | {_cell(st)} | {us} |")
        out.append("")
    out += ["## Cómo procesar lo pendiente", "",
            "- En Claude Code (este repo): `/procesar-nuevas` (todos los cursos) o `/nueva-clase <curso>`.",
            "- Desatendido: `scripts/procesar-nuevas.sh` (no gasta tokens si no hay nada nuevo).",
            "- Detalle, costos y programación: `docs/AUTOMATIZACION.md`.", ""]
    return "\n".join(out)


def write_registry(settings: config.Settings, pend: dict[str, list[dict]] | None = None) -> Path:
    p = config.VAULT / REGISTRY_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(build_registry(settings, pend), encoding="utf-8")
    return p
