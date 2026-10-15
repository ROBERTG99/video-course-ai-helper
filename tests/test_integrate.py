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
    assert "- [[arqui-2026-10-07-clase-15]] — Separar presentación" in t and "00:12:30" not in t
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-14-clase-16") == "updated"
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-14-clase-16") == "unchanged"
    assert (vc / "temas" / "arquitectura-en-capas.md").read_text().count("[[arqui-2026-10-14-clase-16]]") == 1


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


def test_related_titles_resolve_to_real_slugs(tmp_path):
    vc = tmp_path / "arqui"
    other = {"slug": "catalogo-de-atributos-sap", "titulo": "Catálogo de atributos del SAP", "resumen": "x", "timestamps": []}
    cand = {**CAND, "relacionados": ["Catálogo de atributos del SAP", "Algo nuevo"]}
    idx = it.title_index(vc, [other, cand])
    it.upsert_tema(vc, "arqui", cand, "c1", idx)
    t = (vc / "temas" / "arquitectura-en-capas.md").read_text(encoding="utf-8")
    assert "- [[catalogo-de-atributos-sap]]" in t and "- [[algo-nuevo]]" in t
    it.upsert_tema(vc, "arqui", other, "c1", idx)
    assert it.title_index(vc)["catalogo-de-atributos-del-sap"] == "catalogo-de-atributos-sap"


def test_slug_titles(tmp_path):
    vc = tmp_path / "arqui"
    it.upsert_tema(vc, "arqui", CAND, "c1")
    assert it.slug_titles(vc) == {"Arquitectura en capas": "arquitectura-en-capas"}


def test_merge_tema_folds_and_rewrites_links(tmp_path):
    vc = tmp_path / "arqui"
    work = tmp_path / "work"
    (work / "c2").mkdir(parents=True)
    (work / "c2" / "temas-candidatos.json").write_text('[{"slug": "capas"}]', encoding="utf-8")
    it.upsert_tema(vc, "arqui", {**CAND, "relacionados": ["Capas"]}, "c1")
    it.upsert_tema(vc, "arqui", {"slug": "capas", "titulo": "Capas", "resumen": "Otra idea.", "timestamps": ["00:01:00"]}, "c2")
    (vc / "clases").mkdir()
    note = vc / "clases" / "c2.md"
    note.write_text("- [[capas]] y [[capas|las capas]]\n", encoding="utf-8")
    n = it.merge_tema(vc, "capas", "arquitectura-en-capas", tmp_path / "grave", work)
    assert n >= 2 and not (vc / "temas" / "capas.md").exists() and (tmp_path / "grave" / "capas.md").exists()
    assert note.read_text() == "- [[arquitectura-en-capas]] y [[arquitectura-en-capas|las capas]]\n"
    d = (vc / "temas" / "arquitectura-en-capas.md").read_text(encoding="utf-8")
    assert "Otra idea." in d and "- [[arqui-c2]] — Otra idea." in d and "- [[arquitectura-en-capas]]\n" not in d
    assert '"slug": "arquitectura-en-capas"' in (work / "c2" / "temas-candidatos.json").read_text()


def test_relink_dangling(tmp_path):
    vc = tmp_path / "arqui"
    (vc / "temas").mkdir(parents=True)
    for s in ("publish-subscribe", "mongodb-base-no-relacional", "redis", "redis-cache"):
        (vc / "temas" / f"{s}.md").write_text("x", encoding="utf-8")
    t = vc / "temas" / "a.md"
    t.write_text("- [[publish-and-subscribe]]\n- [[mongodb]]\n- [[redis-como-cosa]]\n- [[nada-que-ver]]\n", encoding="utf-8")
    assert it.relink_dangling(vc) == 3
    assert t.read_text() == "- [[publish-subscribe]]\n- [[mongodb-base-no-relacional]]\n- [[redis]]\n- [[nada-que-ver]]\n"
