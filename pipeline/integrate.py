from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

from .config import TEMPLATES, note_name

MARK_START, MARK_END = "<!-- generated:start -->", "<!-- generated:end -->"
DATE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b\d{1,2} de (?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)\b", re.IGNORECASE)


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def title_index(vault_course: Path, cands: list[dict] | None = None) -> dict[str, str]:
    """slugify(title) -> real slug, from existing temas (frontmatter `tema:`) and this batch of candidates."""
    idx: dict[str, str] = {}
    for p in (vault_course / "temas").glob("*.md"):
        m = re.search(r"^tema: (.+)$", p.read_text(encoding="utf-8"), re.MULTILINE)
        idx[slugify(m.group(1) if m else p.stem)] = p.stem
    for c in cands or []:
        idx[slugify(c["titulo"])] = c.get("slug") or slugify(c["titulo"])
    return idx


def slug_titles(vault_course: Path) -> dict[str, str]:
    """Human title -> slug for every existing tema note of the course."""
    out: dict[str, str] = {}
    for p in sorted((vault_course / "temas").glob("*.md")):
        m = re.search(r"^tema: (.+)$", p.read_text(encoding="utf-8"), re.MULTILINE)
        out[m.group(1).strip() if m else p.stem] = p.stem
    return out


def upsert_tema(vault_course: Path, course: str, cand: dict, class_id: str, index: dict[str, str] | None = None) -> str:
    """cand: {slug?, titulo, resumen, relacionados:[titulo]} -> created|updated|unchanged (timestamps are ignored).

    `index` (from title_index) maps related titles to real slugs; unknown titles fall back to slugify.
    """
    slug = cand.get("slug") or slugify(cand["titulo"])
    path = vault_course / "temas" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = cand["resumen"].strip().splitlines()[0][:160]
    note = note_name(course, class_id)
    seen = f"- [[{note}]] — {first}"
    if not path.exists():
        tpl = (TEMPLATES / "tema.md").read_text(encoding="utf-8")
        body = tpl.replace("{{tema}}", cand["titulo"]).replace("curso: \n", f"curso: {course}\n", 1)
        body = body.replace("tema: \n", f"tema: {cand['titulo']}\n", 1)
        body = body.replace("## Ideas clave\n", "## Ideas clave\n" + cand["resumen"].strip() + "\n")
        rel = "".join(f"- [[{(index or {}).get(slugify(r), slugify(r))}]]\n" for r in cand.get("relacionados") or [])
        body = body.replace("## Relacionado\n", "## Relacionado\n" + rel).replace("## Visto en\n", "## Visto en\n" + seen + "\n")
        path.write_text(body, encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8")
    if f"[[{note}]]" in text or f"[[{class_id}]]" in text:  # new or pre-rename link format
        return "unchanged"
    if "## Visto en" not in text:
        text = text.rstrip("\n") + "\n\n## Visto en\n"
    path.write_text(text.rstrip("\n") + "\n" + seen + "\n", encoding="utf-8")
    return "updated"


def regen_moc(vault_course: Path, course: str, full_name: str) -> Path:
    moc = vault_course / f"MOC-{course}.md"
    temas = sorted(p.stem for p in (vault_course / "temas").glob("*.md"))
    clases = sorted(p.stem for p in (vault_course / "clases").glob("*.md"))
    gen = "\n".join([MARK_START, "## Clases", *[f"- [[{c}]]" for c in clases], "", "## Temas (A–Z)",
                     *[f"- [[{t}]]" for t in temas], MARK_END])
    if moc.exists():
        text = moc.read_text(encoding="utf-8")
        if MARK_START in text and MARK_END in text:
            pre, rest = text.split(MARK_START, 1)
            _, post = rest.split(MARK_END, 1)
            text = pre + gen + post
        else:
            text = text.rstrip() + "\n\n" + gen + "\n"
    else:
        text = (f"# {full_name} — mapa de contenido\n\n## Mapa\n"
                "(outline jerárquico editable a mano; el agente integrador lo organiza)\n\n" + gen + "\n")
    moc.write_text(text, encoding="utf-8")
    return moc


def section(text: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.DOTALL | re.MULTILINE)
    return m.group(1).strip() if m else ""


def regen_avisos(vault_course: Path, course: str) -> Path:
    out = [f"# Avisos del profesor — {course}", ""]
    for note in sorted((vault_course / "clases").glob("*.md")):
        body = section(note.read_text(encoding="utf-8"), "⚠️ Avisos del profesor")
        if body and body != "—":
            out += [f"## [[{note.stem}]]", body, ""]
    p = vault_course / f"avisos-{course}.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def regen_calendario(vault: Path, courses: list[str]) -> Path:
    rows = ["# Calendario (líneas de avisos que mencionan una fecha)", "", "| curso | clase | línea |", "|---|---|---|"]
    for c in courses:
        p = vault / c / f"avisos-{c}.md"
        if not p.exists():
            continue
        cur = ""
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("## [["):
                cur = line[3:].strip()
                continue
            if DATE.search(line):
                rows.append(f"| {c} | {cur} | {line.strip().replace('|', '/')} |")
    out = vault / "calendario.md"
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return out


def merge_tema(vault_course: Path, src: str, dst: str, graveyard: Path, work_course: Path | None = None,
               link_roots: list[Path] | None = None) -> int:
    """Fold tema `src` into `dst`: move its ideas and 'Visto en' lines, rewrite [[src]] links across `link_roots`
    (default: the whole `vault_course`; `vault_course` is the dir holding `temas/`) and slugs in
    work/*/temas-candidatos.json, and park the old note in `graveyard`. Returns files rewritten."""
    temas = vault_course / "temas"
    sp, dp = temas / f"{src}.md", temas / f"{dst}.md"
    if not sp.exists() or not dp.exists():
        raise FileNotFoundError(f"merge needs both temas: {sp.name}, {dp.name}")
    s_text, d_text = sp.read_text(encoding="utf-8"), dp.read_text(encoding="utf-8")
    ideas = section(s_text, "Ideas clave")
    if ideas and ideas not in d_text:
        d_text = re.sub(r"^## Ideas clave\n", lambda m: m.group(0) + ideas + "\n", d_text, count=1, flags=re.MULTILINE)
    for line in section(s_text, "Visto en").splitlines():
        m = re.match(r"- \[\[([^\]]+)\]\]", line)
        if m and f"[[{m.group(1)}]]" not in section(d_text, "Visto en"):
            d_text = d_text.rstrip("\n") + "\n" + line + "\n"
    dp.write_text(d_text, encoding="utf-8")
    graveyard.mkdir(parents=True, exist_ok=True)
    sp.replace(graveyard / sp.name)
    link = re.compile(rf"\[\[{re.escape(src)}(?=[\]|#])")
    changed = 0
    files = {p for root in (link_roots or [vault_course]) for p in root.rglob("*.md")}
    for p in sorted(files):
        text = p.read_text(encoding="utf-8")
        new = link.sub(f"[[{dst}", text)
        if p == dp:  # a tema must not list itself as related
            new = re.sub(rf"^- \[\[{re.escape(dst)}\]\]\n", "", new, flags=re.MULTILINE)
        if new != text:
            p.write_text(new, encoding="utf-8")
            changed += 1
    for cj in (work_course.glob("*/temas-candidatos.json") if work_course else []):
        text = cj.read_text(encoding="utf-8")
        new = text.replace(f'"slug": "{src}"', f'"slug": "{dst}"')
        if new != text:
            cj.write_text(new, encoding="utf-8")
    return changed


def closest_slug(name: str, stems: set[str]) -> str | None:
    """Best existing slug for a dangling link: near-identical spelling first, then a unique prefix relation."""
    if name in stems:
        return name
    close = difflib.get_close_matches(name, sorted(stems), n=1, cutoff=0.8)
    if close:
        return close[0]
    pref = [s for s in stems if s.startswith(name + "-") or name.startswith(s + "-")]
    return pref[0] if len(pref) == 1 else None


def relink_dangling(vault_course: Path, known: set[str] | None = None) -> int:
    """Point [[links]] in temas/ that match no note to the closest existing tema. Returns links fixed.

    `known`: when given, the valid link targets are the temas plus these names (e.g. class notes living in the
    vault while temas live in work/); otherwise every note under `vault_course`."""
    temas = vault_course / "temas"
    if known is None:
        stems = {p.stem for p in vault_course.rglob("*.md")}
    else:
        stems = {p.stem for p in temas.glob("*.md")} | known
    fixed = 0
    for p in temas.glob("*.md"):
        text = p.read_text(encoding="utf-8")
        others = stems - {p.stem}

        def repl(m: re.Match, others: set[str] = others) -> str:
            nonlocal fixed
            name = m.group(1).strip()
            if name in stems:
                return m.group(0)
            best = closest_slug(name, others)
            if not best:
                return m.group(0)
            fixed += 1
            return f"[[{best}"

        new = re.sub(r"\[\[([^\]|#]+)(?=[\]|#])", repl, text)
        if new != text:
            p.write_text(new, encoding="utf-8")
    return fixed
