from pipeline import integrate as it

CAND = {"titulo": "Arquitectura en capas", "resumen": "Separar presentación, lógica y datos.\nSegunda línea.",
        "timestamps": ["00:12:30"], "relacionados": ["Acoplamiento y cohesión"]}


def test_slugify():
    assert it.slugify("Acoplamiento y cohesión") == "acoplamiento-y-cohesion"


def test_upsert_tema_create_update_unchanged(tmp_path):
    vc = tmp_path / "arqui"
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-07-clase-15") == "created"
    t = (vc / "temas" / "arquitectura-en-capas.md").read_text(encoding="utf-8")
    assert t.startswith("---\ncurso: arqui\ntema: Arquitectura en capas") and "- [[acoplamiento-y-cohesion]]" in t
    assert "- [[2026-10-07-clase-15]] · 00:12:30 — Separar presentación" in t
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-14-clase-16") == "updated"
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-14-clase-16") == "unchanged"
    assert (vc / "temas" / "arquitectura-en-capas.md").read_text().count("[[2026-10-14-clase-16]]") == 1


def test_regen_moc_preserves_manual_part(tmp_path):
    vc = tmp_path / "arqui"
    (vc / "temas").mkdir(parents=True)
    (vc / "clases").mkdir()
    (vc / "temas" / "capas.md").write_text("x")
    (vc / "clases" / "2026-10-07-clase-15.md").write_text("x")
    moc = it.regen_moc(vc, "arqui", "Arquitectura de Software")
    text = moc.read_text(encoding="utf-8")
    assert "- [[capas]]" in text and "- [[2026-10-07-clase-15]]" in text and text.count(it.MARK_START) == 1
    moc.write_text(text.replace("## Mapa", "## Mapa\n- Manual [[capas]]"), encoding="utf-8")
    (vc / "temas" / "mvc.md").write_text("x")
    text2 = it.regen_moc(vc, "arqui", "Arquitectura de Software").read_text(encoding="utf-8")
    assert "- Manual [[capas]]" in text2 and "- [[mvc]]" in text2 and text2.count(it.MARK_START) == 1


def test_avisos_and_calendario(tmp_path):
    vault = tmp_path
    vc = vault / "arqui"
    (vc / "clases").mkdir(parents=True)
    (vc / "clases" / "2026-10-07-clase-15.md").write_text(
        "## Resumen ejecutivo\nx\n## ⚠️ Avisos del profesor\n- Parcial el 15/10 [00:00:30]\n- Traer laptop\n## Índice de temas\n—\n", encoding="utf-8")
    p = it.regen_avisos(vc, "arqui")
    assert "## [[2026-10-07-clase-15]]" in p.read_text() and "Traer laptop" in p.read_text()
    cal = it.regen_calendario(vault, ["arqui"]).read_text(encoding="utf-8")
    assert "| arqui | [[2026-10-07-clase-15]] | - Parcial el 15/10 [00:00:30] |" in cal and "laptop" not in cal
