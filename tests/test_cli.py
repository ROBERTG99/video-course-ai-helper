import json

from typer.testing import CliRunner

from pipeline import cli_helpers as ch
from pipeline import config, state
from pipeline.__main__ import app

runner = CliRunner()


def test_help_lists_commands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for c in ("list-showcase", "fetch", "transcript", "frames", "prompt", "analyze", "validate", "integrate",
              "canvas", "sync", "status", "init-vault", "strip-timestamps", "units-init", "unit-prompt", "units-finish"):
        assert c in r.output
    assert "integrate-cmd" not in r.output


def test_pending_classes_selects_by_previous_stage(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    a = config.class_dirs("arqui", "2026-09-30-clase-01")["state"]
    b = config.class_dirs("arqui", "2026-10-07-clase-02")["state"]
    state.mark(a, "fetch", "ok")
    state.mark(a, "transcript", "ok")
    state.mark(b, "fetch", "ok")
    assert ch.pending_classes("arqui", "transcript") == ["2026-10-07-clase-02"]
    assert ch.pending_classes("arqui", "frames") == ["2026-09-30-clase-01"]
    assert ch.pending_classes("arqui", "transcript", force=True) == ["2026-09-30-clase-01", "2026-10-07-clase-02"]


def test_status_table(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    sp = config.class_dirs("arqui", "2026-09-30-clase-01")["state"]
    state.set_meta(sp, title="t")
    state.mark(sp, "fetch", "blocked", error="sin VTT")
    r = runner.invoke(app, ["status", "--course", "arqui"])
    assert r.exit_code == 0 and "2026-09-30-clase-01" in r.output and "blocked" in r.output


def test_meta_for_duration_in_minutes(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    cid = "2026-09-30-clase-13"
    sp = config.class_dirs("arqui", cid)["state"]
    state.set_meta(sp, title="T", duration=7001, vimeo_url="https://v/1")
    c = config.Course("arqui", "Arquitectura", "ArqSoft", "u", "p")
    m = ch.meta_for(c, cid)
    assert m["duracion"] == 117 and m["numero"] == 13 and m["fecha"] == "2026-09-30"
    assert m["video_path"] == "—" and m["img_rel"] == f"img/{cid}" and m["nota"] == f"arqui-{cid}"


def test_resolve_path(tmp_path):
    assert ch.resolve_path("raw/x/y.vtt") == config.ROOT / "raw/x/y.vtt"
    assert ch.resolve_path(str(tmp_path / "a.vtt")) == tmp_path / "a.vtt"


def _setup_class(tmp_path, monkeypatch, cid="2026-09-30-clase-01"):
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    monkeypatch.setattr(config, "WORK", tmp_path / "work")
    monkeypatch.setattr(config, "VAULT", tmp_path / "vault")
    return config.class_dirs("arqui", cid)


def test_transcript_command(tmp_path, monkeypatch, repo_root):
    d = _setup_class(tmp_path, monkeypatch)
    state.mark(d["state"], "fetch", "ok", vtt=str(repo_root / "tests/fixtures/sample.vtt"), video=None)
    r = runner.invoke(app, ["transcript", "--course", "arqui"])
    assert r.exit_code == 0, r.output
    out = d["work"] / "transcript.md"
    assert out.exists() and "arquitectura en capas" in out.read_text(encoding="utf-8").lower()
    assert state.is_done(d["state"], "transcript")


def test_transcript_blocked_without_vtt(tmp_path, monkeypatch):
    d = _setup_class(tmp_path, monkeypatch)
    state.mark(d["state"], "fetch", "ok", vtt=None, video=None)
    r = runner.invoke(app, ["transcript", "--course", "arqui"])
    assert r.exit_code == 0
    assert state.load(d["state"])["stages"]["transcript"]["status"] == "blocked"


def test_analyze_agent_marks_ok_when_delivered(tmp_path, monkeypatch):
    d = _setup_class(tmp_path, monkeypatch)
    d["note"].parent.mkdir(parents=True)
    d["note"].write_text("# nota", encoding="utf-8")
    d["work"].mkdir(parents=True)
    (d["work"] / "temas-candidatos.json").write_text(json.dumps([]), encoding="utf-8")
    r = runner.invoke(app, ["analyze", "--course", "arqui", "--class", "2026-09-30-clase-01"])
    assert r.exit_code == 0, r.output
    assert state.load(d["state"])["stages"]["analyze"]["runner"] == "agent"
    assert not (d["work"] / "analysis-prompt.md").exists()


def test_analyze_agent_builds_prompt_when_missing(tmp_path, monkeypatch):
    d = _setup_class(tmp_path, monkeypatch)
    state.set_meta(d["state"], title="T", duration=3600, vimeo_url="https://v/1")
    d["work"].mkdir(parents=True)
    (d["work"] / "transcript.md").write_text("[00:00:00] El parcial es el quince de octubre.\n", encoding="utf-8")
    (d["work"] / "frames.json").write_text(json.dumps({"class_id": "x", "sample_every": 5, "frames": []}), encoding="utf-8")
    r = runner.invoke(app, ["analyze", "--course", "arqui", "--class", "2026-09-30-clase-01"])
    assert r.exit_code == 0, r.output
    assert (d["work"] / "analysis-prompt.md").exists()
    assert not state.is_done(d["state"], "analyze")
    assert "analista-clase" in r.output


def test_avisos_prompt_command(tmp_path, monkeypatch):
    d = _setup_class(tmp_path, monkeypatch)
    d["work"].mkdir(parents=True)
    (d["work"] / "avisos-excerpts.md").write_text("# Fragmentos\n\n## [00:00:30] parcial\nEl parcial es el 15.\n", encoding="utf-8")
    r = runner.invoke(app, ["avisos-prompt", "--course", "arqui", "--class", "2026-09-30-clase-01"])
    assert r.exit_code == 0, r.output
    text = (d["work"] / "avisos-prompt.md").read_text(encoding="utf-8")
    assert "El parcial es el 15." in text and "avisos-review.md" in text and "verificador-avisos" in r.output


MOC_OUTLINE = ("# Arq — mapa de contenido\n\n## Mapa\n- Fundamentos\n  - Qué es\n    - [[capas]]\n- Calidad\n  - [[performance]]\n\n"
               "<!-- generated:start -->\n<!-- generated:end -->\n")
TEMA_MD = "---\ncurso: arqui\ntema: {t}\ntags: [tema]\n---\n# {t}\n\n## Ideas clave\nx\n## Relacionado\n{rel}\n## Visto en\n- [[c1]] — x\n"


def _setup_units(tmp_path, monkeypatch):
    for name in ("STATE", "WORK", "VAULT"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    vc = config.VAULT / "arqui"
    (vc / "temas").mkdir(parents=True)
    (vc / "clases").mkdir()
    (vc / "MOC-arqui.md").write_text(MOC_OUTLINE, encoding="utf-8")
    for slug, t, rel in (("capas", "Capas", ""), ("performance", "Performance", ""), ("latencia", "Latencia", "- [[performance]]")):
        (vc / "temas" / f"{slug}.md").write_text(TEMA_MD.format(t=t, rel=rel), encoding="utf-8")
    (vc / "clases" / "c1.md").write_text("---\nfecha: 2026-08-17\n---\n# C1\n## ⚠️ Avisos del profesor\n- Parcial el 15/10\n"
                                         "## Índice de temas\n- [[capas]] — t\n- [[performance|perf]] — t\n### Capas\n",
                                         encoding="utf-8")
    return vc, config.WORK / "arqui"


def test_units_init(tmp_path, monkeypatch):
    vc, wc = _setup_units(tmp_path, monkeypatch)
    r = runner.invoke(app, ["units-init", "--course", "arqui"])
    assert r.exit_code == 0, r.output
    assert not (vc / "temas").exists() and (wc / "temas" / "capas.md").exists()
    data = json.loads((wc / "units.json").read_text(encoding="utf-8"))
    assert [u["slug"] for u in data] == ["01-fundamentos", "02-calidad"]
    assert data[1]["groups"] == [{"name": None, "temas": ["performance", "latencia"]}]
    assert "huérfano latencia -> 02-calidad" in r.output
    r2 = runner.invoke(app, ["units-init", "--course", "arqui"])
    assert r2.exit_code == 0 and "ya existe" in r2.output


def test_unit_prompt_and_finish(tmp_path, monkeypatch):
    vc, wc = _setup_units(tmp_path, monkeypatch)
    assert runner.invoke(app, ["units-init", "--course", "arqui"]).exit_code == 0
    r = runner.invoke(app, ["unit-prompt", "--course", "arqui"])
    assert r.exit_code == 0, r.output
    assert (wc / "units" / "01-fundamentos.prompt.md").exists() and (wc / "units" / "02-calidad.prompt.md").exists()
    r = runner.invoke(app, ["unit-prompt", "--course", "arqui", "--update", "latencia"])
    assert r.exit_code == 0 and "02-calidad.prompt.md" in r.output and "01-fundamentos" not in r.output
    assert "MODO ACTUALIZACIÓN" in (wc / "units" / "02-calidad.prompt.md").read_text(encoding="utf-8")

    r = runner.invoke(app, ["units-finish", "--course", "arqui"])
    assert r.exit_code == 1 and "falta el documento" in r.output
    assert "[[capas]]" in (vc / "clases" / "c1.md").read_text(encoding="utf-8")  # untouched on error

    (vc / "unidades").mkdir()
    (vc / "unidades" / "01-fundamentos.md").write_text(
        "# Fundamentos\n> Base.\n## Mapa de la unidad\n## Qué es\n### Capas lógicas\nVer en clase: [[c1#Capas|Clase 1]]\n",
        encoding="utf-8")
    (vc / "unidades" / "02-calidad.md").write_text("# Calidad\n> Atributos.\n## Atributos\n### Performance\n", encoding="utf-8")
    (wc / "units" / "01-fundamentos.map.json").write_text(json.dumps({"capas": "Capas lógicas"}), encoding="utf-8")
    (wc / "units" / "02-calidad.map.json").write_text(json.dumps({"performance": "Performance", "latencia": "Performance"}),
                                                     encoding="utf-8")
    r = runner.invoke(app, ["units-finish", "--course", "arqui"])
    assert r.exit_code == 0, r.output
    note = (vc / "clases" / "c1.md").read_text(encoding="utf-8")
    assert "- [[01-fundamentos#Capas lógicas|Capas]] — t" in note and "- [[02-calidad#Performance|perf]] — t" in note
    moc = (vc / "MOC-arqui.md").read_text(encoding="utf-8")
    assert "1. [[01-fundamentos|Fundamentos]] — Base." in moc and "   - [[01-fundamentos#Qué es|Qué es]]" in moc
    cv = json.loads((vc / "MOC-arqui.canvas").read_text(encoding="utf-8"))
    assert any(n.get("subpath") == "#Atributos" for n in cv["nodes"])
    assert "Parcial el 15/10" in (vc / "avisos-arqui.md").read_text(encoding="utf-8")
    assert (config.VAULT / "calendario.md").exists()
    assert "- [[02-calidad|Calidad]]" in (config.VAULT / "00-MOC-2026.md").read_text(encoding="utf-8")
    assert "links con problemas:" in r.output
    # unit docs are never overwritten by the pipeline
    assert (vc / "unidades" / "02-calidad.md").read_text(encoding="utf-8").startswith("# Calidad\n> Atributos.")


def test_integrate_units_mode_assign(tmp_path, monkeypatch):
    vc, wc = _setup_units(tmp_path, monkeypatch)
    assert runner.invoke(app, ["units-init", "--course", "arqui"]).exit_code == 0
    cid = "2026-09-30-clase-02"
    d = config.class_dirs("arqui", cid)
    state.mark(d["state"], "validate", "ok")
    d["work"].mkdir(parents=True)
    (d["work"] / "temas-candidatos.json").write_text(json.dumps([
        {"titulo": "Caché distribuida", "resumen": "Redis como caché.", "relacionados": ["Performance"]},
        {"slug": "capas", "titulo": "Capas", "resumen": "Más capas."}]), encoding="utf-8")
    r = runner.invoke(app, ["integrate", "--course", "arqui"])
    assert r.exit_code == 0, r.output
    assert (wc / "temas" / "cache-distribuida.md").exists() and not (vc / "temas").exists()
    assert f"- [[arqui-{cid}]] — Más capas." in (wc / "temas" / "capas.md").read_text(encoding="utf-8")
    assert "cache-distribuida" in r.output and "--assign" in r.output
    assert "## Unidades" in (vc / "MOC-arqui.md").read_text(encoding="utf-8")
    r = runner.invoke(app, ["integrate", "--course", "arqui", "--assign", "cache-distribuida=02-calidad"])
    assert r.exit_code == 0, r.output
    data = json.loads((wc / "units.json").read_text(encoding="utf-8"))
    assert data[1]["groups"][-1]["temas"][-1] == "cache-distribuida"
    assert "temas NUEVOS" not in r.output


def test_strip_timestamps_command(tmp_path, monkeypatch):
    vc, _ = _setup_units(tmp_path, monkeypatch)
    (vc / "clases" / "c2.md").write_text("- [00:01:00] [[capas]] — t\nalgo [00:02:00].\n", encoding="utf-8")
    r = runner.invoke(app, ["strip-timestamps", "--course", "arqui"])
    assert r.exit_code == 0 and "timestamps removidos: 2 en 2 notas" in r.output
    assert (vc / "clases" / "c2.md").read_text(encoding="utf-8") == "- [[capas]] — t\nalgo.\n"


def test_rename_notes_command(tmp_path, monkeypatch):
    for name in ("STATE", "WORK", "VAULT"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    cid = "2026-08-17-clase-01"
    (config.VAULT / "arqui" / "clases").mkdir(parents=True)
    (config.VAULT / "arqui" / "clases" / f"{cid}.md").write_text(f"[[{cid}#A]]\n", encoding="utf-8")
    r = runner.invoke(app, ["rename-notes", "--course", "arqui"])
    assert r.exit_code == 0, r.output
    assert "notas renombradas 1; links reescritos 1 en 1 archivos" in r.output
    assert (config.VAULT / "arqui" / "clases" / f"arqui-{cid}.md").read_text(encoding="utf-8") == f"[[arqui-{cid}#A]]\n"
