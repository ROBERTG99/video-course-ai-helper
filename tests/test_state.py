import pytest

from pipeline import state


def test_mark_and_is_done(tmp_path):
    p = tmp_path / "s" / "c.json"
    assert not state.is_done(p, "fetch")
    st = state.mark(p, "fetch", "ok", vtt="x.vtt")
    assert st["stages"]["fetch"]["vtt"] == "x.vtt" and state.is_done(p, "fetch")
    state.mark(p, "fetch", "blocked", error="sin VTT")
    assert not state.is_done(p, "fetch")


def test_set_meta_keeps_stages(tmp_path):
    p = tmp_path / "c.json"
    state.mark(p, "fetch", "ok")
    st = state.set_meta(p, course="arqui", class_id="2026-10-07-clase-15")
    assert st["course"] == "arqui" and state.is_done(p, "fetch")


def test_unknown_stage_rejected(tmp_path):
    with pytest.raises(ValueError):
        state.mark(tmp_path / "c.json", "nope", "ok")


def test_next_pending(tmp_path):
    p = tmp_path / "c.json"
    state.mark(p, "fetch", "ok")
    assert state.next_pending(p) == "transcript"
