from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import TEMPLATES

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


def upsert_tema(vault_course: Path, course: str, cand: dict, class_id: str, index: dict[str, str] | None = None) -> str:
    """cand: {slug?, titulo, resumen, timestamps:[hh:mm:ss], relacionados:[titulo]} -> created|updated|unchanged.

    `index` (from title_index) maps related titles to real slugs; unknown titles fall back to slugify.
    """
    slug = cand.get("slug") or slugify(cand["titulo"])
    path = vault_course / "temas" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = cand["resumen"].strip().splitlines()[0][:160]
    seen = f"- [[{class_id}]] · {', '.join(cand.get('timestamps') or [])} — {first}"
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
    if f"[[{class_id}]]" in text:
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
