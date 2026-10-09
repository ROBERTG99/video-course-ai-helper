from pathlib import Path

from pipeline import vtt

FIX = Path(__file__).parent / "fixtures" / "sample.vtt"


def test_parse_merges_repeated_cues_and_joins_lines():
    cues = vtt.parse(FIX)
    assert [c.text for c in cues] == [
        "Buenas, arrancamos la clase.",
        "Hoy vemos arquitectura en capas y el patron MVC.",
        "El parcial es el quince de octubre.",
    ]
    assert cues[0].start == 0.0 and cues[0].end == 6.0


def test_hms():
    assert vtt.hms(0) == "00:00:00" and vtt.hms(3661.9) == "01:01:01"


def test_paragraphs_every_30s():
    paras = vtt.paragraphs(vtt.parse(FIX), every=30)
    assert [p[0] for p in paras] == [0.0, 40.0]
    assert paras[0][1].startswith("Buenas") and "MVC" in paras[0][1]


def test_glossary_applied(tmp_path):
    g = tmp_path / "g.txt"
    g.write_text("patron MVC => patrón MVC  # typo frecuente\n")
    md = vtt.to_markdown(vtt.parse(FIX), "arqui · c1", every=30, glossary=vtt.load_glossary(g))
    assert "[00:00:00]" in md and "patrón MVC" in md and md.startswith("# Transcript · arqui · c1")


def test_convert_writes_file(tmp_path):
    out = tmp_path / "t.md"
    n = vtt.convert(FIX, out, "x")
    assert n == 3 and out.read_text().count("\n[") == 2
