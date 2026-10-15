import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from pipeline import __main__ as cli
from pipeline import config, registry, state
from pipeline.vimeo import ShowcaseVideo, VimeoShowcase

runner = CliRunner()

VIDS = [  # chronological: ids 2026-08-17-clase-01 .. 2026-08-31-clase-04
    ShowcaseVideo("101", "Clase | 17-08-2026", 7200, "2026-08-18T05:00:00+00:00", "https://player/101"),
    ShowcaseVideo("102", "Clase | 19-08-2026", 6000, "2026-08-20T05:00:00+00:00", "https://player/102"),
    ShowcaseVideo("103", "Clase | 24-08-2026", 5400, "2026-08-25T05:00:00+00:00", "https://player/103"),
    ShowcaseVideo("104", "Clase | 31-08-2026", 3000, "2026-09-01T05:00:00+00:00", "https://player/104"),
]
C1, C2, C3, C4 = "2026-08-17-clase-01", "2026-08-19-clase-02", "2026-08-24-clase-03", "2026-08-31-clase-04"


def _settings(tmp_path: Path, password: str = "pw") -> config.Settings:
    c = config.Course("arqui", "Arquitectura de Software", "ArqSoft", "https://vimeo.com/showcase/123", password)
    return config.Settings({"arqui": c}, {}, {}, [], tmp_path / "Drive")


@pytest.fixture
def env(tmp_path, monkeypatch):
    for name in ("STATE", "WORK", "VAULT"):
        monkeypatch.setattr(config, name, tmp_path / name.lower())
    monkeypatch.setattr(VimeoShowcase, "list_videos", lambda self: list(VIDS))
    s = _settings(tmp_path)
    monkeypatch.setattr(cli, "_settings", lambda: s)
    # C1 complete (note + units), C2 stuck at frames, C3 blocked at fetch, C4 never fetched
    sp = lambda cid: config.class_dirs("arqui", cid)["state"]
    for st in state.STAGES:
        state.mark(sp(C1), st, "ok")
    state.set_meta(sp(C1), title=VIDS[0].title, duration=7200, video_id="101")
    state.mark(sp(C2), "fetch", "ok")
    state.mark(sp(C2), "transcript", "ok")
    state.set_meta(sp(C2), title=VIDS[1].title, duration=6000)
    state.mark(sp(C3), "fetch", "blocked", error="sin VTT en Vimeo")
    note = config.class_dirs("arqui", C1)["note"]
    note.parent.mkdir(parents=True)
    note.write_text("# C1\n", encoding="utf-8")
    wc = config.WORK / "arqui"
    (wc / C1).mkdir(parents=True)
    (wc / C1 / "temas-candidatos.json").write_text(json.dumps([{"slug": "capas", "titulo": "Capas"},
                                                              {"titulo": "Latencia"}]), encoding="utf-8")
    (wc / "units.json").write_text(json.dumps([
        {"num": 1, "name": "Fundamentos", "slug": "01-fundamentos", "groups": [{"name": None, "temas": ["capas"]}]},
        {"num": 2, "name": "Calidad", "slug": "02-calidad", "groups": [{"name": None, "temas": ["latencia"]}]},
        {"num": 3, "name": "Estilos", "slug": "03-estilos", "groups": [{"name": None, "temas": ["capas-x"]}]},
    ]), encoding="utf-8")
    (wc / "units").mkdir()
    (wc / "units" / "01-fundamentos.map.json").write_text(json.dumps({"capas": "Capas"}), encoding="utf-8")
    (wc / "units" / "02-calidad.map.json").write_text(json.dumps({"latencia": "Latencia"}), encoding="utf-8")
    (wc / "units" / "03-estilos.map.json").write_text(json.dumps({"capas-x": "X"}), encoding="utf-8")
    return s


def _by_id(rows):
    return {r["class_id"]: r for r in rows}


def test_pending_online_statuses(env):
    rows = _by_id(registry.pending(env)["arqui"])
    assert set(rows) == {C2, C3, C4}  # C1 complete: not listed
    assert rows[C2]["status"] == "incompleta:frames"
    assert rows[C3]["status"] == "bloqueada:fetch: sin VTT en Vimeo"
    assert rows[C4] == {"class_id": C4, "video_id": "104", "title": "Clase | 31-08-2026", "duration_min": 50,
                        "status": "nueva"}


def test_pending_offline_only_state(env, monkeypatch):
    monkeypatch.setattr(VimeoShowcase, "list_videos", lambda self: pytest.fail("offline must not hit the network"))
    rows = _by_id(registry.pending(env, online=False)["arqui"])
    assert set(rows) == {C2, C3}
    assert rows[C2]["duration_min"] == 100


def test_pending_network_error_becomes_row(env, monkeypatch):
    def boom(self):
        raise ConnectionError("vimeo down")

    monkeypatch.setattr(VimeoShowcase, "list_videos", boom)
    rows = registry.pending(env)["arqui"]
    assert rows[0]["status"] == "error: vimeo down" and {r["class_id"] for r in rows[1:]} == {C2, C3}
    no_pw = _settings(config.VAULT.parent, password="")
    assert registry.pending(no_pw)["arqui"][0]["status"].startswith("error: missing ARQUI_VIMEO_URL")


def test_pending_cli_exit_codes(env, monkeypatch):
    r = runner.invoke(cli.app, ["pending", "--json"])
    assert r.exit_code == 3, r.output
    assert {x["class_id"] for x in json.loads(r.output)["arqui"]} == {C2, C3, C4}
    r = runner.invoke(cli.app, ["pending", "--course", "arqui"])
    assert r.exit_code == 3 and "incompleta:frames" in r.output
    for cid in (C2, C3):
        for st in state.STAGES:
            state.mark(config.class_dirs("arqui", cid)["state"], st, "ok")
    monkeypatch.setattr(VimeoShowcase, "list_videos", lambda self: VIDS[:3])
    r = runner.invoke(cli.app, ["pending"])
    assert r.exit_code == 0 and "Nada pendiente" in r.output

    def boom(self):
        raise ConnectionError("down")

    monkeypatch.setattr(VimeoShowcase, "list_videos", boom)
    assert runner.invoke(cli.app, ["pending"]).exit_code == 4


def test_build_registry_content(env):
    text = registry.build_registry(env, registry.pending(env))
    assert text.startswith("# Registro de clases 2026\n\nActualizado: 20")
    pend = text.split("## Pendientes", 1)[1].split("## Arquitectura de Software", 1)[0]
    assert f"| arqui | {C4} | Clase \\| 31-08-2026 | nueva |" in pend
    assert f"| arqui | {C2} |" in pend and C1 not in pend
    course = text.split("## Arquitectura de Software", 1)[1].split("## Cómo procesar", 1)[0]
    assert f"| 1 | [[arqui-{C1}\\|17/08]] | 120 | ✅ | [[01-fundamentos\\|01]] [[02-calidad\\|02]] |" in course
    assert "| 2 | 19/08 | 100 | incompleta:frames | — |" in course  # no note yet: plain date, no broken link
    assert "| 3 | 24/08 | 0 | bloqueada:fetch: sin VTT en Vimeo | — |" in course
    assert "| 4 | 31/08 | 50 | nueva | — |" in course
    tail = text.split("## Cómo procesar lo pendiente", 1)[1]
    assert "/procesar-nuevas" in tail and "scripts/procesar-nuevas.sh" in tail and "docs/AUTOMATIZACION.md" in tail


def test_registry_nothing_pending_and_cli(env, monkeypatch):
    assert "Nada pendiente: todas las clases publicadas están procesadas." in registry.build_registry(env, {"arqui": []})
    monkeypatch.setattr(VimeoShowcase, "list_videos", lambda self: pytest.fail("offline must not hit the network"))
    r = runner.invoke(cli.app, ["registry", "--offline"])
    assert r.exit_code == 0, r.output
    text = (config.VAULT / "clases-registro.md").read_text(encoding="utf-8")
    assert f"| arqui | {C2} |" in text and C4 not in text


def test_class_units_uses_visto_en_of_merged_temas(env):
    wc = config.WORK / "arqui"
    (wc / "temas").mkdir()
    (wc / "temas" / "capas-x.md").write_text(f"---\ntema: X\n---\n# X\n## Visto en\n- [[arqui-{C2}]] — x\n",
                                             encoding="utf-8")
    cu = registry.class_units("arqui")
    assert [u.slug for u in cu[C1]] == ["01-fundamentos", "02-calidad"]
    assert [u.slug for u in cu[C2]] == ["03-estilos"]


def test_sync_root_copies_registry(env, tmp_path):
    (config.VAULT).mkdir(parents=True, exist_ok=True)
    (config.VAULT / "clases-registro.md").write_text("reg", encoding="utf-8")
    (tmp_path / "Drive").mkdir()
    r = runner.invoke(cli.app, ["sync-root"])
    assert r.exit_code == 0, r.output
    assert (tmp_path / "Drive" / "clases-registro.md").read_text(encoding="utf-8") == "reg"
