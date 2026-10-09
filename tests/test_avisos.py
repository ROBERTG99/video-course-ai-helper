from pipeline import avisos

T = """# Transcript · x

[00:00:00] arrancamos con capas
[00:00:30] el parcial es el quince de octubre
[00:01:00] sigamos con MVC
[00:03:00] la entrega del obligatorio es el viernes
"""


def test_excerpts_with_context(tmp_path):
    p = tmp_path / "t.md"
    p.write_text(T, encoding="utf-8")
    paras = avisos.read_transcript(p)
    assert paras[1] == (30, "el parcial es el quince de octubre")
    hits = avisos.excerpts(paras, ["parcial", "entrega", "obligatorio"], context=60)
    assert [h["t"] for h in hits] == [30, 180]
    assert hits[0]["keywords"] == ["parcial"] and "arrancamos" in hits[0]["text"] and "MVC" in hits[0]["text"]
    assert hits[1]["keywords"] == ["entrega", "obligatorio"]
    md = avisos.to_markdown(hits)
    assert md.startswith("# Fragmentos") and "## [00:00:30] parcial" in md
