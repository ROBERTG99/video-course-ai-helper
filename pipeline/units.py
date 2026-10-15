from __future__ import annotations

import difflib
import json
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from . import config
from .canvas import outline
from .integrate import section, slugify
from .note_validate import frontmatter

WIKI = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:#[^\]|]*)?(?:\|[^\]]*)?\]\]")
ANY_WIKI = re.compile(r"(?<!!)\[\[([^\]]+)\]\]")
HEADING = re.compile(r"^#{1,6}[ \t]+(.+?)[ \t]*$", re.MULTILINE)
SKIP_H2 = {"Mapa de la unidad", "Avisos del profesor sobre esta unidad"}


@dataclass
class Unit:
    num: int
    name: str
    groups: list[tuple[str | None, list[str]]] = field(default_factory=list)

    @property
    def slug(self) -> str:
        return f"{self.num:02d}-{slugify(self.name)}"

    @property
    def temas(self) -> list[str]:
        return [t for _, ts in self.groups for t in ts]

    def add_tema(self, slug: str) -> None:
        """Append to the last group (creating an unnamed one if the unit has none)."""
        if slug in self.temas:
            return
        if not self.groups:
            self.groups.append((None, []))
        self.groups[-1][1].append(slug)


def _label_text(label: str) -> str:
    """Outline label without wikilink syntax: [[a|b]] -> b, [[a]] -> a."""
    return re.sub(r"\[\[([^\]|]+)(?:\|([^\]]*))?\]\]", lambda m: m.group(2) or m.group(1), label).strip()


def parse_outline(moc_text: str) -> list[Unit]:
    """Units from the MOC's '## Mapa' outline. Depth 0 text = unit; depth 1 text = group, depth 1 [[slug]] = unnamed
    group; any deeper [[slug]] belongs to the current depth-1 group. A slug is kept only at its first appearance."""
    m = re.search(r"^## Mapa[ \t]*\n(.*?)(?=^## |<!-- generated:start -->|\Z)", moc_text, re.DOTALL | re.MULTILINE)
    if not m:
        return []
    units: list[Unit] = []
    seen: set[str] = set()
    group: tuple[str | None, list[str]] | None = None
    for depth, label in outline(m.group(1)):
        link = WIKI.search(label)
        if depth == 0:
            units.append(Unit(len(units) + 1, _label_text(label)))
            group = None
            continue
        if not units:
            continue
        unit = units[-1]
        if depth == 1 and not link:
            group = (label, [])
            unit.groups.append(group)
            continue
        if not link:
            continue  # deeper text-only line: a sub-heading, its temas stay in the depth-1 group
        # a depth-1 [[slug]] opens an unnamed group (consecutive ones share it); deeper ones need any group
        if group is None or (depth == 1 and group[0] is not None):
            group = (None, [])
            unit.groups.append(group)
        slug = link.group(1).strip()
        if slug not in seen:
            seen.add(slug)
            group[1].append(slug)
    return units


def save_units(path: Path, units: list[Unit]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = [{"num": u.num, "name": u.name, "slug": u.slug,
             "groups": [{"name": g, "temas": ts} for g, ts in u.groups]} for u in units]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_units(path: Path) -> list[Unit]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [Unit(d["num"], d["name"], [(g["name"], list(g["temas"])) for g in d["groups"]]) for d in data]


def archive_temas(vault_course: Path, work_course: Path) -> int:
    """Move vault/<c>/temas/*.md into work/<c>/temas/ (vault version wins) and drop the emptied dir. Returns moved."""
    src = vault_course / "temas"
    if not src.is_dir():
        return 0
    dest = work_course / "temas"
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    for p in sorted(src.glob("*.md")):
        shutil.move(str(p), str(dest / p.name))
        n += 1
    if not any(src.iterdir()):
        src.rmdir()
    return n


def _body(text: str) -> str:
    m = re.match(r"^---\n.*?\n---\n", text, re.DOTALL)
    return text[m.end():] if m else text


def tema_info(work_course: Path, slug: str) -> dict:
    """Title, body and class ids ('Visto en') of an internal tema note; `work_course` is work/<curso>."""
    p = work_course / "temas" / f"{slug}.md"
    if not p.exists():
        return {"slug": slug, "titulo": slug, "text": "", "clases": []}
    text = p.read_text(encoding="utf-8")
    titulo = frontmatter(text).get("tema") or slug
    clases: list[str] = []
    prefix = f"{work_course.name}-"  # 'Visto en' links are note names `<curso>-<class_id>` (or bare pre-rename ids)
    for line in section(text, "Visto en").splitlines():
        m = re.match(r"\s*- \[\[([^\]|#]+)", line)
        cid = m.group(1).strip().removeprefix(prefix) if m else ""
        if cid and cid not in clases:
            clases.append(cid)
    return {"slug": slug, "titulo": titulo, "text": _body(text).strip(), "clases": clases}


def related(work_course: Path, slug: str) -> list[str]:
    """Slugs listed under '## Relacionado' of a tema."""
    p = work_course / "temas" / f"{slug}.md"
    if not p.exists():
        return []
    return [m.group(1).strip() for m in WIKI.finditer(section(p.read_text(encoding="utf-8"), "Relacionado"))]


def headings(text: str, levels: tuple[int, ...] = (1, 2, 3, 4, 5, 6)) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"^(#{1,6})[ \t]+(.+?)[ \t]*$", text, re.MULTILINE):
        if len(m.group(1)) in levels:
            out.append(m.group(2).strip())
    return out


def unit_h2s(doc: Path) -> list[str]:
    """The unit doc's ## sections, without the navigation/avisos ones."""
    if not doc.exists():
        return []
    return [h for h in headings(doc.read_text(encoding="utf-8"), (2,)) if h not in SKIP_H2]


def doc_path(vault_course: Path, unit: Unit) -> Path:
    return vault_course / "unidades" / f"{unit.slug}.md"


def map_path(work_course: Path, unit: Unit) -> Path:
    return work_course / "units" / f"{unit.slug}.map.json"


def build_unit_prompt(course_slug: str, full_name: str, unit: Unit, all_units: list[Unit], vault_course: Path,
                      work_course: Path, update_temas: list[str] | None = None) -> str:
    role = (config.PROMPTS / "redactor-unidad.md").read_text(encoding="utf-8")
    meta = {"curso": course_slug, "nombre_curso": full_name,
            "unidad": {"num": unit.num, "name": unit.name, "slug": unit.slug},
            "unidades_del_curso": [{"slug": u.slug, "name": u.name} for u in all_units]}
    infos = {t: tema_info(work_course, t) for t in unit.temas}
    parts = [role, "## Metadatos\n```json\n" + json.dumps(meta, ensure_ascii=False, indent=1) + "\n```",
             (f"## Salidas\n- Documento: `{doc_path(vault_course, unit).resolve()}`\n"
              f"- Mapa: `{map_path(work_course, unit).resolve()}`")]
    if update_temas:
        parts.append(f"MODO ACTUALIZACIÓN: integrá solo estos temas nuevos: {', '.join(update_temas)}")
    lines = ["## Outline de la unidad"]
    for g, ts in unit.groups:
        lines.append(f"### {g or '(sin grupo)'}")
        lines += [f"- {t} — {infos[t]['titulo']}" for t in ts]
    parts.append("\n".join(lines))
    parts.append("## Notas internas de temas\n\n" + "\n\n".join(
        f"### {t} — {infos[t]['titulo']}\n{infos[t]['text'] or '—'}" for t in unit.temas))
    cids = sorted({c for i in infos.values() for c in i["clases"]})
    blocks = ["## Notas de clase a consultar"]
    for cid in cids:
        name = config.note_name(course_slug, cid)
        note = vault_course / "clases" / f"{name}.md"
        hs = headings(note.read_text(encoding="utf-8"), (3,)) if note.exists() else []
        blocks.append(f"### {name}\n- Link: `[[{name}#<H3>|Clase N (dd/mm)]]`\n- Ruta: `{note.resolve()}`"
                      + ("" if note.exists() else " (NO EXISTE)") + "\n" + "\n".join(f"  - `### {h}`" for h in hs))
    parts.append("\n\n".join(blocks))
    return "\n\n".join(parts) + "\n"


def load_map(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8"))


def check_map(doc: Path, map_file: Path, unit: Unit) -> list[str]:
    errs: list[str] = []
    if not doc.exists():
        errs.append(f"{unit.slug}: falta el documento {doc}")
    if not map_file.exists():
        errs.append(f"{unit.slug}: falta el mapa {map_file}")
    if errs:
        return errs
    try:
        mp = load_map(map_file)
    except json.JSONDecodeError as e:
        return [f"{unit.slug}: mapa JSON inválido ({e})"]
    if not isinstance(mp, dict):
        return [f"{unit.slug}: el mapa no es un objeto JSON"]
    heads = set(headings(doc.read_text(encoding="utf-8"), (2, 3)))
    errs += [f"{unit.slug}: tema '{t}' no está en el mapa" for t in unit.temas if t not in mp]
    errs += [f"{unit.slug}: '{t}' -> heading inexistente '{h}'" for t, h in mp.items() if str(h).strip() not in heads]
    return errs


def _alias(s: str) -> str:
    return s.replace("|", "/").replace("[", "(").replace("]", ")").strip()


def relink_classes(vault_course: Path, maps: dict[str, tuple[str, str]], titles: dict[str, str]) -> int:
    """[[tema]] / [[tema|alias]] in class notes -> [[unit#Heading|alias]] (alias defaults to the tema title)."""
    pat = re.compile(r"(?<!!)\[\[([^\]|#]+)(\|[^\]]*)?\]\]")
    total = 0
    for p in sorted((vault_course / "clases").glob("*.md")):
        text = p.read_text(encoding="utf-8")
        n = 0

        def repl(m: re.Match) -> str:
            nonlocal n
            slug = m.group(1).strip()
            if slug not in maps:
                return m.group(0)
            unit_slug, heading = maps[slug]
            alias = m.group(2)[1:] if m.group(2) else _alias(titles.get(slug) or slug)
            n += 1
            return f"[[{unit_slug}#{heading.strip()}|{alias}]]"

        new = pat.sub(repl, text)
        if new != text:
            p.write_text(new, encoding="utf-8")
            total += n
    return total


def _strip_code(text: str) -> str:
    text = re.sub(r"^(```|~~~).*?^\1[ \t]*$", "", text, flags=re.DOTALL | re.MULTILINE)
    return re.sub(r"`[^`\n]*`", "", text)


def check_links(vault: Path, files: list[Path] | None = None) -> list[str]:
    """Wikilinks whose note or heading does not exist, plus note basenames repeated in the vault (Obsidian resolves
    `[[name]]` by basename, so a repeated one is ambiguous). Notes resolve by basename over the whole vault."""
    all_md = sorted(vault.rglob("*.md"))
    by_name: dict[str, Path] = {}
    dups: dict[str, list[Path]] = {}
    for p in all_md:
        if p.stem in by_name:
            dups.setdefault(p.stem, [by_name[p.stem]]).append(p)
        by_name.setdefault(p.stem, p)
    other = {p.name for p in vault.rglob("*") if p.is_file() and p.suffix != ".md"}
    heads_cache: dict[Path, set[str]] = {}
    errs: list[str] = [f"basename duplicado: {name} ({', '.join(p.relative_to(vault).as_posix() for p in ps)})"
                       for name, ps in sorted(dups.items())]
    for f in files if files is not None else all_md:
        rel = f.relative_to(vault).as_posix()
        for m in ANY_WIKI.finditer(_strip_code(f.read_text(encoding="utf-8"))):
            target = re.split(r"\\?\|", m.group(1), maxsplit=1)[0]
            note, _, heading = target.partition("#")
            note = note.strip()
            if not note:
                continue
            name = note.rsplit("/", 1)[-1].removesuffix(".md")
            dest = by_name.get(name)
            if dest is None:
                if name not in other:
                    errs.append(f"{rel}: [[{m.group(1)}]] — nota inexistente")
                continue
            heading = heading.split("#")[-1].strip()
            if not heading or heading.startswith("^"):
                continue
            if dest not in heads_cache:
                heads_cache[dest] = set(headings(dest.read_text(encoding="utf-8")))
            if heading not in heads_cache[dest]:
                errs.append(f"{rel}: [[{m.group(1)}]] — heading inexistente en {dest.stem}")
    return errs


def _first_quote(doc: Path) -> str:
    if not doc.exists():
        return ""
    for line in doc.read_text(encoding="utf-8").splitlines():
        if line.startswith("> "):
            return line[2:].strip()
    return ""


def _fecha(note: Path) -> str:
    f = frontmatter(note.read_text(encoding="utf-8")).get("fecha", "")
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", f)
    return f"{m.group(3)}/{m.group(2)}/{m.group(1)}" if m else f


def regen_moc_units(vault_course: Path, course: str, full_name: str, units: list[Unit]) -> Path:
    out = [f"# {full_name} — mapa del curso", "", "## Unidades"]
    for i, u in enumerate(units, 1):
        doc = doc_path(vault_course, u)
        resumen = _first_quote(doc)
        out.append(f"{i}. [[{u.slug}|{_alias(u.name)}]]" + (f" — {resumen}" if resumen else ""))
        out += [f"   - [[{u.slug}#{h}|{_alias(h)}]]" for h in unit_h2s(doc)]
    out += ["", "## Clases"]
    for note in sorted((vault_course / "clases").glob("*.md")):
        fecha = _fecha(note)
        out.append(f"- [[{note.stem}]]" + (f" — {fecha}" if fecha else ""))
    out += ["", "## Avisos y calendario", f"- [[avisos-{course}]]", "- [[calendario]]", ""]
    moc = vault_course / f"MOC-{course}.md"
    moc.write_text("\n".join(out), encoding="utf-8")
    return moc


def regen_root_moc(vault: Path, courses: dict[str, str], work: Path | None = None) -> Path:
    work = work or config.WORK
    out = ["# 2026 — cursos", ""]
    for slug, full_name in courses.items():
        out += [f"## {full_name}", f"- [[MOC-{slug}]]"]
        uj = work / slug / "units.json"
        if uj.exists():
            out += [f"- [[{u.slug}|{_alias(u.name)}]]" for u in load_units(uj)]
        out.append("")
    out += ["- [[calendario]]", ""]
    p = vault / "00-MOC-2026.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def assign_orphans(units: list[Unit], work_course: Path) -> list[tuple[str, str]]:
    """Temas in work/<c>/temas/ that are in no unit go to the unit sharing most of their 'Relacionado' temas
    (ties: the earliest such unit; none: the last unit). Returns [(tema, unit_slug)]."""
    if not units:
        return []
    placed = {t for u in units for t in u.temas}
    out: list[tuple[str, str]] = []
    for p in sorted((work_course / "temas").glob("*.md")):
        if p.stem in placed:
            continue
        rel = set(related(work_course, p.stem))
        best, score = units[-1], 0
        for u in units:
            s = len(rel & set(u.temas))
            if s > score:
                best, score = u, s
        best.add_tema(p.stem)
        placed.add(p.stem)
        out.append((p.stem, best.slug))
    return out


def rename_tema(work_course: Path, src: str, dst: str) -> None:
    """After merging tema src into dst: fix units.json and unit maps so src disappears (dst takes its place)."""
    uj = work_course / "units.json"
    if not uj.exists():
        return
    units = load_units(uj)
    has_dst = any(dst in u.temas for u in units)
    for u in units:
        for _, ts in u.groups:
            if src in ts:
                if has_dst:
                    ts.remove(src)
                else:
                    ts[ts.index(src)] = dst
                    has_dst = True
    save_units(uj, units)
    for mf in (work_course / "units").glob("*.map.json"):
        mp = load_map(mf)
        if src not in mp:
            continue
        h = mp.pop(src)
        mp.setdefault(dst, h)
        mf.write_text(json.dumps(mp, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def _norm_heading(s: str) -> str:
    s = re.sub(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", lambda w: w.group(2) or w.group(1), s)
    return re.sub(r"[^\w]+", " ", s.lower()).strip()


def fix_anchors(vault: Path, files: list[Path]) -> int:
    """Re-point `[[note#Heading]]` anchors that do not match a heading of the target note to its closest heading."""
    by_name = {p.stem: p for p in sorted(vault.rglob("*.md"))}
    cache: dict[Path, list[str]] = {}
    fixed = 0
    for f in files:
        text = f.read_text(encoding="utf-8")

        def repl(m: re.Match) -> str:
            nonlocal fixed
            note, heading, alias = m.group(1), m.group(2).strip(), m.group(3)
            dest = by_name.get(note.strip())
            if dest is None:
                return m.group(0)
            if dest not in cache:
                cache[dest] = headings(dest.read_text(encoding="utf-8"))
            heads = cache[dest]
            if heading in heads:
                return m.group(0)
            norm = {_norm_heading(h): h for h in heads}
            key = _norm_heading(heading)
            best = norm.get(key)
            if best is None:
                cands = [h for k, h in norm.items() if key and (key in k or k in key)]
                best = cands[0] if len(cands) == 1 else None
            if best is None:
                close = difflib.get_close_matches(key, list(norm), n=1, cutoff=0.75)
                best = norm[close[0]] if close else None
            if best is None:
                return m.group(0)
            fixed += 1
            return f"[[{note}#{best}{'|' + alias if alias else ''}]]"

        new = re.sub(r"\[\[([^\]|#]+)#([^\]|]+)(?:\|([^\]]+))?\]\]", repl, text)
        if new != text:
            f.write_text(new, encoding="utf-8")
    return fixed
