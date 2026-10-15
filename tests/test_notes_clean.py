from pipeline import notes_clean as nc


def s(text: str) -> str:
    return nc.strip_timestamps(text)


def test_index_line_and_heading():
    assert s("- [00:07:14] [[enfoque-de-la-materia]] — De qué trata") == "- [[enfoque-de-la-materia]] — De qué trata"
    assert s("### Enfoque de la materia [00:07:14]") == "### Enfoque de la materia"


def test_quote_and_que_muestra():
    assert s('- Se aprueba con 70 — "Con 70 puntos se aprueba." [00:18:15]') == '- Se aprueba con 70 — "Con 70 puntos se aprueba."'
    assert s("Qué muestra: slide de capas [00:41:00]") == "Qué muestra: slide de capas"
    assert s('"uno" [00:23:04]; "dos" [00:23:34]') == '"uno"; "dos"'


def test_sequences_and_ranges():
    assert s("vistas (módulos, asignación) [01:28:59] [01:35:29] [01:44:27].") == "vistas (módulos, asignación)."
    assert s("Grafana (3000) [01:36:45]–[01:45:22]. Luego") == "Grafana (3000). Luego"
    assert s("decoración / concepto [00:16:23-00:34:11].") == "decoración / concepto."
    assert s("cosa [01:20:39, 01:56:26].") == "cosa."
    assert s("x [00:30:22 a 00:32:56]. Conclusión") == "x. Conclusión"
    assert s("a [00:01:00], [00:02:00]; b [00:03:00][00:04:00] c") == "a; b c"


def test_parens_prepositions_and_list_markers():
    assert s("audio ([00:00:48]-[00:04:24]), el profesor") == "audio, el profesor"
    assert s("- confirmado en [01:05:08].") == "- confirmado."
    assert s("- [00:40:16]: el profesor dice") == "- el profesor dice"
    assert s("  - 23/09 [00:40:16]: verificar") == "  - 23/09: verificar"
    assert s("en .NET y [00:01:00] en .md") == "en .NET y en .md"


def test_empty_lines_removed_blank_lines_kept():
    assert s("a\n- [00:01:00]\n\nb [00:02:00]\n[00:03:00]\nc") == "a\n\nb\nc"


def test_frontmatter_and_code_untouched():
    text = "---\ncurso: arqui\nhora: [00:01:00]\n---\n# T [00:01:00]\n```\nlog [00:02:00]\n```\nfin [00:03:00].\n"
    assert s(text) == "---\ncurso: arqui\nhora: [00:01:00]\n---\n# T\n```\nlog [00:02:00]\n```\nfin.\n"


def test_unbracketed_and_links_untouched():
    text = "Hueco entre 00:19:11 y 01:25:38; ver [[2026-08-17-clase-01]] y [00:01:00](http://x)."
    assert s(text) == text


def test_strip_file(tmp_path):
    p = tmp_path / "n.md"
    p.write_text("a [00:01:00] [00:02:00].\n- [00:03:00–00:04:00] [[x]] — t\n", encoding="utf-8")
    assert nc.strip_file(p) == 4
    assert p.read_text(encoding="utf-8") == "a.\n- [[x]] — t\n"
    mtime = p.stat().st_mtime_ns
    assert nc.strip_file(p) == 0 and p.stat().st_mtime_ns == mtime


def test_plain_headings():
    from pipeline.notes_clean import plain_headings
    text = "## Desarrollo por tema\n### [[cqrs]] — CQRS: modelos\ntexto [[cqrs]]\n### Uso de [[redis|Redis]] como caché\n"
    out, n = plain_headings(text)
    assert n == 2
    assert "### CQRS: modelos\n" in out and "### Uso de Redis como caché\n" in out and "texto [[cqrs]]" in out
