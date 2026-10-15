from pipeline import migrate

CID = "2026-08-17-clase-01"
CID2 = "2026-08-19-clase-02"


def _vault(tmp_path):
    vault, work, state = tmp_path / "vault", tmp_path / "work", tmp_path / "state"
    for c in ("arqui", "isa2"):
        (vault / c / "clases" / "img" / CID).mkdir(parents=True)
        (vault / c / "unidades").mkdir(parents=True)
        (state / c).mkdir(parents=True)
        (state / c / f"{CID}.json").write_text("{}", encoding="utf-8")
        (vault / c / "clases" / f"{CID}.md").write_text(
            f"# {c}\n### Tema A\n![](img/{CID}/0001.jpg)\nVer [[{CID}#Tema A]]\n", encoding="utf-8")
        (vault / c / "MOC-{c}.md".replace("{c}", c)).write_text(f"## Clases\n- [[{CID}]] — 17/08/2026\n", encoding="utf-8")
        (vault / c / f"avisos-{c}.md").write_text(f"# Avisos\n## [[{CID}]]\n- Parcial 15/10\n", encoding="utf-8")
    (state / "arqui" / f"{CID2}.json").write_text("{}", encoding="utf-8")
    (vault / "arqui" / "clases" / f"{CID2}.md").write_text(f"Ver [[{CID}|la clase 1]] y ![[{CID}]]\n", encoding="utf-8")
    (vault / "arqui" / "unidades" / "01-u.md").write_text(
        f"Ver en clase: [[{CID}#Tema A|Clase 1 (17/08)]], [[{CID2}#Desarrollo por tema|Clase 2]]\n"
        f"| t | [[{CID}\\|Clase 1]] |\n[[01-u#X]] [[otra-{CID}]]\n", encoding="utf-8")
    (work / "arqui" / "temas").mkdir(parents=True)
    (work / "arqui" / "temas" / "capas.md").write_text(f"## Visto en\n- [[{CID}]] — x\n- [[{CID2}]] — y\n", encoding="utf-8")
    (vault / "calendario.md").write_text(
        f"| curso | clase | línea |\n|---|---|---|\n| arqui | [[{CID}]] | - Parcial 15/10 |\n"
        f"| isa2 | [[{CID}]] | - TP 20/10 |\n", encoding="utf-8")
    return vault, work, state


def test_rename_notes_same_class_id_two_courses(tmp_path):
    vault, work, state = _vault(tmp_path)
    r = migrate.rename_notes("arqui", vault, work, state)
    assert r.renamed == 2 and r.links == 11 and r.files == 7
    ac = vault / "arqui" / "clases"
    assert sorted(p.name for p in ac.glob("*.md")) == [f"arqui-{CID}.md", f"arqui-{CID2}.md"]
    assert (ac / "img" / CID).is_dir()
    note = (ac / f"arqui-{CID}.md").read_text(encoding="utf-8")
    assert f"![](img/{CID}/0001.jpg)" in note and f"[[arqui-{CID}#Tema A]]" in note
    assert (ac / f"arqui-{CID2}.md").read_text(encoding="utf-8") == f"Ver [[arqui-{CID}|la clase 1]] y ![[arqui-{CID}]]\n"
    unit = (vault / "arqui" / "unidades" / "01-u.md").read_text(encoding="utf-8")
    assert f"[[arqui-{CID}#Tema A|Clase 1 (17/08)]], [[arqui-{CID2}#Desarrollo por tema|Clase 2]]" in unit
    assert f"| t | [[arqui-{CID}\\|Clase 1]] |" in unit and f"[[otra-{CID}]]" in unit
    assert f"- [[arqui-{CID}]] — x\n- [[arqui-{CID2}]] — y" in (work / "arqui" / "temas" / "capas.md").read_text()
    cal = (vault / "calendario.md").read_text(encoding="utf-8")
    assert f"| arqui | [[arqui-{CID}]] |" in cal and f"| isa2 | [[{CID}]] |" in cal
    # the other course is untouched until its own run
    assert (vault / "isa2" / "clases" / f"{CID}.md").read_text(encoding="utf-8").endswith(f"[[{CID}#Tema A]]\n")
    r2 = migrate.rename_notes("isa2", vault, work, state)
    assert r2.renamed == 1
    assert (vault / "isa2" / "clases" / f"isa2-{CID}.md").exists()
    assert f"## [[isa2-{CID}]]" in (vault / "isa2" / "avisos-isa2.md").read_text(encoding="utf-8")
    cal = (vault / "calendario.md").read_text(encoding="utf-8")
    assert f"| arqui | [[arqui-{CID}]] |" in cal and f"| isa2 | [[isa2-{CID}]] |" in cal


def test_rename_notes_idempotent(tmp_path):
    vault, work, state = _vault(tmp_path)
    migrate.rename_notes("arqui", vault, work, state)
    snap = {p: p.read_text(encoding="utf-8") for p in sorted(tmp_path.rglob("*.md"))}
    r = migrate.rename_notes("arqui", vault, work, state)
    assert (r.renamed, r.links, r.files) == (0, 0, 0)
    assert {p: p.read_text(encoding="utf-8") for p in sorted(tmp_path.rglob("*.md"))} == snap
    assert not any("arqui-arqui-" in t for t in snap.values())


def test_rename_notes_keeps_existing_new_note(tmp_path):
    vault, work, state = _vault(tmp_path)
    (vault / "arqui" / "clases" / f"arqui-{CID}.md").write_text("nueva\n", encoding="utf-8")
    r = migrate.rename_notes("arqui", vault, work, state)
    assert r.renamed == 1  # only CID2; the old CID note is left for review, the new one is not overwritten
    assert (vault / "arqui" / "clases" / f"arqui-{CID}.md").read_text(encoding="utf-8") == "nueva\n"
    assert (vault / "arqui" / "clases" / f"{CID}.md").exists()


def test_course_class_ids(tmp_path):
    vault, work, state = _vault(tmp_path)
    (vault / "arqui" / "clases" / "notas-sueltas.md").write_text("x", encoding="utf-8")
    assert migrate.course_class_ids("arqui", state / "arqui", vault / "arqui") == [CID, CID2]
    migrate.rename_notes("arqui", vault, work, state)
    assert migrate.course_class_ids("arqui", tmp_path / "nada", vault / "arqui") == [CID, CID2]
