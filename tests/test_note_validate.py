from pathlib import Path

from pipeline import note_validate as nv

GOOD = """---
curso: arqui
fecha: 2026-10-07
numero: 15
titulo: Capas
duracion: 7010
vimeo_url: https://vimeo.com/showcase/1/video/2
video_path: raw/arqui/x/video.mp4
estado: borrador
tags: [clase]
---
# arqui · Clase 15
## Resumen ejecutivo
Vimos capas [00:01:00].
## ⚠️ Avisos del profesor
—
## Índice de temas
- [[arquitectura-en-capas]]
## Desarrollo por tema
![](img/c/0001.jpg)
## Conceptos y definiciones
—
## Ejemplos, demos y código
—
## Preguntas de alumnos y respuestas
—
## Dudas / a verificar
—
## Citas textuales relevantes
—
## Material referenciado
—
"""


def make(tmp_path: Path, text: str) -> tuple[Path, Path]:
    vault = tmp_path / "vault"
    (vault / "arqui" / "clases" / "img" / "c").mkdir(parents=True)
    (vault / "arqui" / "temas").mkdir()
    (vault / "arqui" / "temas" / "arquitectura-en-capas.md").write_text("# t")
    (vault / "arqui" / "clases" / "img" / "c" / "0001.jpg").write_bytes(b"x")
    note = vault / "arqui" / "clases" / "c.md"
    note.write_text(text, encoding="utf-8")
    return note, vault


def test_valid_note_has_no_errors(tmp_path):
    note, vault = make(tmp_path, GOOD)
    assert nv.validate(note, vault) == []


def test_detects_problems(tmp_path):
    bad = (
        GOOD.replace("## Índice de temas\n", "")
        .replace("0001.jpg", "0009.jpg")
        .replace("[[arquitectura-en-capas]]", "[[nope]]")
        .replace("[00:01:00]", "")
    )
    bad = bad.replace("estado: borrador\n", "")
    note, vault = make(tmp_path, bad)
    errs = nv.validate(note, vault)
    assert any("Índice de temas" in e for e in errs)
    assert any("0009.jpg" in e for e in errs)
    assert any("[[nope]]" in e for e in errs)
    assert any("timestamps" in e for e in errs)
    assert any("'estado'" in e for e in errs)


def test_section_order(tmp_path):
    swapped = GOOD.replace(
        "## Resumen ejecutivo\nVimos capas [00:01:00].\n## ⚠️ Avisos del profesor\n—\n",
        "## ⚠️ Avisos del profesor\n—\n## Resumen ejecutivo\nVimos capas [00:01:00].\n",
    )
    note, vault = make(tmp_path, swapped)
    assert "secciones fuera de orden" in nv.validate(note, vault)
