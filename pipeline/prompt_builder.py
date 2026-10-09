from __future__ import annotations

import json
from pathlib import Path

from .config import PROMPTS, TEMPLATES
from .vtt import hms


def frames_table(manifest: Path, max_ocr: int = 200) -> str:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    rows = ["| t | archivo | OCR (recorte) |", "|---|---|---|"]
    for f in data["frames"]:
        if not f["keep"]:
            continue
        ocr = f["ocr"][:max_ocr].replace("|", "/")
        rows.append(f"| {hms(f['t'])}–{hms(f['t_end'])} | {Path(f['file']).name} | {ocr} |")
    return "\n".join(rows)


def build_analysis_prompt(
    meta: dict, transcript: Path, manifest: Path, note_path: Path, temas_path: Path, img_rel: str
) -> str:
    role = (PROMPTS / "analista-clase.md").read_text(encoding="utf-8")
    template = (TEMPLATES / "clase.md").read_text(encoding="utf-8")
    return "\n\n".join([
        role,
        "## Metadatos\n```json\n" + json.dumps(meta, ensure_ascii=False, indent=1) + "\n```",
        (
            "## Salidas obligatorias\n"
            f"- Nota: `{note_path}`\n- Temas candidatos: `{temas_path}`\n"
            f"- Las imágenes se referencian como `![]({img_rel}/<archivo>)` usando solo archivos de la tabla de frames."
        ),
        "## Plantilla de la nota (respetar frontmatter, secciones y orden)\n```markdown\n" + template + "\n```",
        "## Frames disponibles (podés abrir el archivo con Read para verlo)\n" + frames_table(manifest),
        "## Transcript\n" + transcript.read_text(encoding="utf-8"),
    ])


def build_avisos_prompt(meta: dict, excerpts_md: Path, note_path: Path, review_path: Path) -> str:
    role = (PROMPTS / "verificador-avisos.md").read_text(encoding="utf-8")
    return "\n\n".join([
        role,
        "## Metadatos\n```json\n" + json.dumps(meta, ensure_ascii=False, indent=1) + "\n```",
        (
            f"## Entradas\n- Nota a revisar: `{note_path}` (leer solo la sección ⚠️ Avisos del profesor)\n- Fragmentos: abajo\n"
            f"## Salida\n- Escribir el informe en `{review_path}`"
        ),
        excerpts_md.read_text(encoding="utf-8"),
    ])
