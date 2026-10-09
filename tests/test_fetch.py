from pipeline import config, fetch, state
from pipeline.vimeo import ShowcaseVideo


def _course():
    return config.Course("arqui", "Arq", "ArqSoft", "https://vimeo.com/showcase/9", "pw")


def test_fetch_course_marks_ok_and_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw")
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    monkeypatch.setattr(config, "WORK", tmp_path / "work")
    monkeypatch.setattr(config, "VAULT", tmp_path / "vault")
    vids = [ShowcaseVideo("1", "a | 30-09-2026", 10, "2026-10-01T00:00:00+00:00", "u1"),
            ShowcaseVideo("2", "b | 07-10-2026", 10, "2026-10-08T00:00:00+00:00", "u2")]
    monkeypatch.setattr(fetch.VimeoShowcase, "list_videos", lambda self: vids)

    def fake_download(video, dest, subs_only):
        dest.mkdir(parents=True, exist_ok=True)
        if video.video_id == "1":
            (dest / "video.es-x-autogen.vtt").write_text("WEBVTT\n")
            return {"vtt": str(dest / "video.es-x-autogen.vtt"), "video": None, "subs_langs": ["es-x-autogen"]}
        return {"vtt": None, "video": None, "subs_langs": []}

    monkeypatch.setattr(fetch, "download", fake_download)
    res = fetch.fetch_course(_course(), subs_only=True)
    assert [r["class_id"] for r in res] == ["2026-09-30-clase-01", "2026-10-07-clase-02"]
    s1 = state.load(config.class_dirs("arqui", "2026-09-30-clase-01")["state"])
    s2 = state.load(config.class_dirs("arqui", "2026-10-07-clase-02")["state"])
    assert s1["stages"]["fetch"]["status"] == "ok" and s1["title"] == "a | 30-09-2026"
    assert s2["stages"]["fetch"]["status"] == "blocked" and "sin VTT" in s2["stages"]["fetch"]["error"]
    # second run with subs_only skips the ok one
    res2 = fetch.fetch_course(_course(), subs_only=True)
    assert res2[0].get("skipped") is True


def test_ydl_opts_contract(tmp_path):
    o = fetch.ydl_opts(tmp_path, subs_only=True, max_height=720)
    assert o["skip_download"] is True and o["subtitleslangs"] == ["all"]
    assert o["http_headers"]["Referer"] == "https://vimeo.com/"
    assert o["format"].startswith("bv*[height<=720]")


def test_pick_vtt_prefers_autogen(tmp_path):
    (tmp_path / "video.en.vtt").write_text("WEBVTT\n")
    (tmp_path / "video.es-x-autogen.vtt").write_text("WEBVTT\n")
    assert fetch.pick_vtt(tmp_path).name == "video.es-x-autogen.vtt"
    (tmp_path / "video.es-x-autogen.vtt").unlink()
    assert fetch.pick_vtt(tmp_path).name == "video.en.vtt"
    (tmp_path / "video.en.vtt").unlink()
    assert fetch.pick_vtt(tmp_path) is None


def test_store_relative_under_root(tmp_path):
    assert fetch._store(config.ROOT / "raw" / "x" / "video.vtt") == "raw/x/video.vtt"
    assert fetch._store(tmp_path / "v.vtt") == str(tmp_path / "v.vtt")
