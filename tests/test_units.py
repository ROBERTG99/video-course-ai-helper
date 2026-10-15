import json

from pipeline import config
from pipeline import units as un

MOC = """# Arq — mapa de contenido

## Mapa
- Fundamentos
  - Qué es
    - [[definicion]]
      - [[anidado]]
    - Subgrupo de texto
      - [[profundo]]
  - [[suelto]]
  - [[suelto-2]]
- Calidad y tácticas
  - Atributos
    - [[performance]]
    - [[definicion]]

<!-- generated:start -->
- [[ignorado]]
<!-- generated:end -->
"""

TEMA = """---
curso: arqui
tema: {titulo}
tags: [tema]
---
# {titulo}

## Definición
## Ideas clave
Idea de {slug}.
## Relacionado
{rel}
## Visto en
{seen}
"""


def write_tema(work_course, slug, titulo, clases=(), rel=()):
    p = work_course / "temas" / f"{slug}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(TEMA.format(slug=slug, titulo=titulo, rel="\n".join(f"- [[{r}]]" for r in rel),
                             seen="\n".join(f"- [[{c}]] — algo" for c in clases)), encoding="utf-8")
    return p


def test_parse_outline_groups():
    us = un.parse_outline(MOC)
    assert [u.slug for u in us] == ["01-fundamentos", "02-calidad-y-tacticas"]
    f = us[0]
    assert f.groups == [("Qué es", ["definicion", "anidado", "profundo"]), (None, ["suelto", "suelto-2"])]
    assert f.temas == ["definicion", "anidado", "profundo", "suelto", "suelto-2"]
    assert us[1].groups == [("Atributos", ["performance"])]  # duplicate slug kept only at first appearance
    assert un.parse_outline("# X\n- [[a]]\n") == []


def test_save_load_roundtrip(tmp_path):
    us = un.parse_outline(MOC)
    p = tmp_path / "units.json"
    un.save_units(p, us)
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data[0]["slug"] == "01-fundamentos" and data[0]["groups"][1] == {"name": None, "temas": ["suelto", "suelto-2"]}
    back = un.load_units(p)
    assert [(u.num, u.name, u.groups) for u in back] == [(u.num, u.name, u.groups) for u in us]


def test_archive_temas(tmp_path):
    vc, wc = tmp_path / "vault" / "arqui", tmp_path / "work" / "arqui"
    (vc / "temas").mkdir(parents=True)
    (vc / "temas" / "a.md").write_text("nuevo")
    (vc / "temas" / "b.md").write_text("b")
    (wc / "temas").mkdir(parents=True)
    (wc / "temas" / "a.md").write_text("viejo")
    assert un.archive_temas(vc, wc) == 2
    assert not (vc / "temas").exists()
    assert (wc / "temas" / "a.md").read_text() == "nuevo" and (wc / "temas" / "b.md").exists()
    assert un.archive_temas(vc, wc) == 0


def test_archive_keeps_nonempty_dir(tmp_path):
    vc, wc = tmp_path / "vault" / "arqui", tmp_path / "work" / "arqui"
    (vc / "temas").mkdir(parents=True)
    (vc / "temas" / "a.md").write_text("a")
    (vc / "temas" / "otra.txt").write_text("x")
    assert un.archive_temas(vc, wc) == 1 and (vc / "temas" / "otra.txt").exists()


def test_tema_info(tmp_path):
    wc = tmp_path / "arqui"
    write_tema(wc, "capas", "Arquitectura en capas", ["c1", "arqui-c2", "arqui-c1"])
    i = un.tema_info(wc, "capas")  # bare ids and `<curso>-<id>` note names both map to the class id
    assert i["titulo"] == "Arquitectura en capas" and i["clases"] == ["c1", "c2"]
    assert i["text"].startswith("# Arquitectura en capas") and "curso:" not in i["text"]
    assert un.tema_info(wc, "nope") == {"slug": "nope", "titulo": "nope", "text": "", "clases": []}


def _course(tmp_path):
    vc, wc = tmp_path / "vault" / "arqui", tmp_path / "work" / "arqui"
    (vc / "clases").mkdir(parents=True)
    (vc / "clases" / "arqui-c1.md").write_text("---\nfecha: 2026-08-17\n---\n# C1\n## Desarrollo por tema\n### Capas y niveles\n"
                                         "### MVC\n- [[definicion]] y [[definicion|la def]] y [[c2]] y ![[img.png]]\n",
                                         encoding="utf-8")
    write_tema(wc, "definicion", "Definición de arquitectura", ["c1"])
    write_tema(wc, "performance", "Performance", ["arqui-c1", "c9"])  # new and pre-rename 'Visto en' formats
    return vc, wc


def test_build_unit_prompt(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "PROMPTS", tmp_path / "prompts")
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "redactor-unidad.md").write_text("# Rol: redactor\n", encoding="utf-8")
    vc, wc = _course(tmp_path)
    us = un.parse_outline(MOC)
    p = un.build_unit_prompt("arqui", "Arquitectura", us[1], us, vc, wc)
    assert p.startswith("# Rol: redactor")
    assert '"slug": "02-calidad-y-tacticas"' in p and '"slug": "01-fundamentos"' in p
    assert str((vc / "unidades" / "02-calidad-y-tacticas.md").resolve()) in p
    assert str((wc / "units" / "02-calidad-y-tacticas.map.json").resolve()) in p
    assert "### Atributos\n- performance — Performance" in p
    assert "### performance — Performance\n# Performance" in p and "Idea de performance." in p
    assert str((vc / "clases" / "arqui-c1.md").resolve()) in p and "`### Capas y niveles`" in p and "`### MVC`" in p
    assert "### arqui-c1\n- Link: `[[arqui-c1#" in p
    assert "arqui-c9.md` (NO EXISTE)" in p
    assert "MODO ACTUALIZACIÓN" not in p
    p2 = un.build_unit_prompt("arqui", "Arquitectura", us[1], us, vc, wc, ["performance"])
    assert "MODO ACTUALIZACIÓN: integrá solo estos temas nuevos: performance" in p2


def test_check_map(tmp_path):
    us = un.parse_outline(MOC)
    u = us[1]
    doc, mp = tmp_path / "doc.md", tmp_path / "map.json"
    assert len(un.check_map(doc, mp, u)) == 2
    doc.write_text("# Calidad\n## Atributos\n### Performance y latencia\n", encoding="utf-8")
    mp.write_text(json.dumps({"performance": "Performance y latencia"}), encoding="utf-8")
    assert un.check_map(doc, mp, u) == []
    mp.write_text(json.dumps({"performance": "No existe", "otro": "Atributos"}), encoding="utf-8")
    assert un.check_map(doc, mp, u) == ["02-calidad-y-tacticas: 'performance' -> heading inexistente 'No existe'"]
    mp.write_text(json.dumps({"otro": "Atributos"}), encoding="utf-8")
    assert un.check_map(doc, mp, u) == ["02-calidad-y-tacticas: tema 'performance' no está en el mapa"]


def test_relink_classes(tmp_path):
    vc, _ = _course(tmp_path)
    n = un.relink_classes(vc, {"definicion": ("01-fundamentos", "Qué es")}, {"definicion": "Definición | arq"})
    assert n == 2
    t = (vc / "clases" / "arqui-c1.md").read_text(encoding="utf-8")
    assert "[[01-fundamentos#Qué es|Definición / arq]] y [[01-fundamentos#Qué es|la def]] y [[c2]] y ![[img.png]]" in t
    assert un.relink_classes(vc, {"definicion": ("01-fundamentos", "Qué es")}, {}) == 0


def test_check_links(tmp_path):
    vault = tmp_path / "vault"
    (vault / "arqui" / "unidades").mkdir(parents=True)
    (vault / "arqui" / "unidades" / "01-u.md").write_text("# U\n## Grupo\n### Concepto A\n- [[#Grupo]]\n", encoding="utf-8")
    (vault / "arqui" / "img.png").write_bytes(b"x")
    note = vault / "arqui" / "n.md"
    note.write_text("[[01-u#Concepto A|a]] [[01-u#Concepto B|b]] [[01-u]] [[nada]] [[img.png]] ![[otra.png]]\n"
                    "`[[en-codigo]]`\n```\n[[en-bloque]]\n```\n", encoding="utf-8")
    errs = un.check_links(vault)
    assert errs == ["arqui/n.md: [[01-u#Concepto B|b]] — heading inexistente en 01-u",
                    "arqui/n.md: [[nada]] — nota inexistente"]
    assert un.check_links(vault, [vault / "arqui" / "unidades" / "01-u.md"]) == []


def test_check_links_flags_duplicate_basenames(tmp_path):
    vault = tmp_path / "vault"
    for c in ("arqui", "isa2"):
        (vault / c / "clases").mkdir(parents=True)
        (vault / c / "clases" / "2026-08-17-clase-01.md").write_text("# x\n", encoding="utf-8")
    assert un.check_links(vault) == [
        "basename duplicado: 2026-08-17-clase-01 (arqui/clases/2026-08-17-clase-01.md, isa2/clases/2026-08-17-clase-01.md)"]


def test_regen_moc_units(tmp_path):
    vc, _ = _course(tmp_path)
    (vc / "clases" / "arqui-c2.md").write_text("# sin frontmatter\n", encoding="utf-8")
    us = un.parse_outline(MOC)
    (vc / "unidades").mkdir()
    (vc / "unidades" / "01-fundamentos.md").write_text(
        "---\ncurso: arqui\n---\n# Fundamentos\n> Qué es la arquitectura.\n\n## Mapa de la unidad\n- x\n## Qué es\n### A\n"
        "## Sin grupo\n## Avisos del profesor sobre esta unidad\n", encoding="utf-8")
    text = un.regen_moc_units(vc, "arqui", "Arquitectura de Software", us).read_text(encoding="utf-8")
    assert text.startswith("# Arquitectura de Software — mapa del curso\n\n## Unidades\n")
    assert ("1. [[01-fundamentos|Fundamentos]] — Qué es la arquitectura.\n"
            "   - [[01-fundamentos#Qué es|Qué es]]\n   - [[01-fundamentos#Sin grupo|Sin grupo]]\n"
            "2. [[02-calidad-y-tacticas|Calidad y tácticas]]\n") in text
    assert "Mapa de la unidad" not in text and "Avisos del profesor" not in text
    assert "## Clases\n- [[arqui-c1]] — 17/08/2026\n- [[arqui-c2]]\n" in text
    assert text.endswith("## Avisos y calendario\n- [[avisos-arqui]]\n- [[calendario]]\n")


def test_regen_root_moc(tmp_path):
    vault, work = tmp_path / "vault", tmp_path / "work"
    vault.mkdir()
    un.save_units(work / "arqui" / "units.json", un.parse_outline(MOC))
    text = un.regen_root_moc(vault, {"arqui": "Arquitectura", "dbpt": "DBPT"}, work).read_text(encoding="utf-8")
    assert text == ("# 2026 — cursos\n\n## Arquitectura\n- [[MOC-arqui]]\n- [[01-fundamentos|Fundamentos]]\n"
                    "- [[02-calidad-y-tacticas|Calidad y tácticas]]\n\n## DBPT\n- [[MOC-dbpt]]\n\n- [[calendario]]\n")


def test_assign_orphans_and_rename(tmp_path):
    wc = tmp_path / "work" / "arqui"
    us = un.parse_outline(MOC)
    write_tema(wc, "latencia", "Latencia", rel=["performance", "suelto-x"])
    write_tema(wc, "huerfano", "Huérfano")
    write_tema(wc, "performance", "Performance")
    assert un.assign_orphans(us, wc) == [("huerfano", "02-calidad-y-tacticas"), ("latencia", "02-calidad-y-tacticas")]
    assert us[1].groups == [("Atributos", ["performance", "huerfano", "latencia"])]
    un.save_units(wc / "units.json", us)
    (wc / "units").mkdir()
    (wc / "units" / "02-calidad-y-tacticas.map.json").write_text(json.dumps({"latencia": "L", "performance": "P"}))
    un.rename_tema(wc, "latencia", "performance")
    assert un.load_units(wc / "units.json")[1].temas == ["performance", "huerfano"]
    assert json.loads((wc / "units" / "02-calidad-y-tacticas.map.json").read_text()) == {"performance": "P"}


def test_fix_anchors(tmp_path):
    from pipeline import units as u
    v = tmp_path / "vault"
    (v / "c" / "clases").mkdir(parents=True)
    (v / "c" / "clases" / "k1.md").write_text("## Desarrollo por tema\n### CQRS: modelos, sincronización\n", encoding="utf-8")
    doc = v / "c" / "u.md"
    doc.write_text("Ver: [[k1#cqrs — CQRS: modelos, sincronización|Clase 1]] y [[k1#Nada que ver|x]]\n", encoding="utf-8")
    assert u.fix_anchors(v, [doc]) == 1
    assert "[[k1#CQRS: modelos, sincronización|Clase 1]]" in doc.read_text()
