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
              "canvas", "sync", "status", "init-vault"):
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
    assert m["video_path"] == "—" and m["img_rel"] == f"img/{cid}"


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
