from __future__ import annotations

import re
from pathlib import Path

REQUIRED_FM = ["curso", "fecha", "numero", "titulo", "duracion", "vimeo_url", "video_path", "estado", "tags"]
REQUIRED_H2 = ["Resumen ejecutivo", "⚠️ Avisos del profesor", "Índice de temas", "Desarrollo por tema",
               "Conceptos y definiciones", "Ejemplos, demos y código", "Preguntas de alumnos y respuestas",
               "Dudas / a verificar", "Citas textuales relevantes", "Material referenciado"]
IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
TS = re.compile(r"\[\d\d:\d\d:\d\d\]")


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def validate(note: Path, vault: Path) -> list[str]:
    text = note.read_text(encoding="utf-8")
    errs: list[str] = []
    fm = frontmatter(text)
    if not fm:
        errs.append("frontmatter ausente")
    for k in REQUIRED_FM:
        if not fm.get(k):
            errs.append(f"frontmatter sin '{k}'")
    heads = [h.strip() for h in re.findall(r"^## (.+)$", text, re.MULTILINE)]
    for h in REQUIRED_H2:
        if h not in heads:
            errs.append(f"falta sección '## {h}'")
    order = [heads.index(h) for h in REQUIRED_H2 if h in heads]
    if order != sorted(order):
        errs.append("secciones fuera de orden")
    for rel in IMG.findall(text):
        if not rel.startswith("http") and not (note.parent / rel).exists():
            errs.append(f"imagen inexistente: {rel}")
    names = {p.stem for p in vault.rglob("*.md")}
    for link in WIKI.findall(text):
        if link.strip() not in names:
            errs.append(f"wikilink roto: [[{link}]]")
    if not TS.search(text):
        errs.append("sin timestamps [hh:mm:ss]")
    return errs
