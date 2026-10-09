import pytest

from pipeline import sync


def test_move_raw(tmp_path):
    raw = tmp_path / "raw" / "arqui" / "c1"
    raw.mkdir(parents=True)
    (raw / "video.mp4").write_bytes(b"v")
    (raw / "video.es.vtt").write_text("w")
    dest = sync.move_raw(raw, tmp_path / "dump", "arqui", "c1")
    assert (dest / "video.mp4").exists() and (dest / "video.es.vtt").exists()
    assert not any(raw.iterdir())


def test_move_raw_target_exists(tmp_path):
    raw = tmp_path / "raw" / "arqui" / "c1"
    raw.mkdir(parents=True)
    (raw / "same.mp4").write_bytes(b"abc")
    (raw / "diff.vtt").write_text("newer-longer")
    dest = tmp_path / "dump" / "arqui" / "c1"
    dest.mkdir(parents=True)
    (dest / "same.mp4").write_bytes(b"xyz")  # same size: kept as is
    (dest / "diff.vtt").write_text("old")  # different size: overwritten
    sync.move_raw(raw, tmp_path / "dump", "arqui", "c1")
    assert (dest / "same.mp4").read_bytes() == b"xyz"
    assert (dest / "diff.vtt").read_text() == "newer-longer"
    assert not any(raw.iterdir())


def test_mirror_vault(tmp_path):
    vc = tmp_path / "vault" / "arqui"
    (vc / "clases").mkdir(parents=True)
    (vc / ".obsidian").mkdir()
    (vc / "clases" / "c1.md").write_text("n")
    (vc / ".obsidian" / "x").write_text("x")
    drive_course = tmp_path / "Drive" / "ArqSoft"
    sync.mirror_vault(vc, drive_course)
    assert (drive_course / "notas" / "clases" / "c1.md").exists()
    assert not (drive_course / "notas" / ".obsidian").exists()
    (vc / "clases" / "c1.md").unlink()
    sync.mirror_vault(vc, drive_course)
    assert not (drive_course / "notas" / "clases" / "c1.md").exists()


def test_mirror_vault_keeps_existing_obsidian_in_dest(tmp_path):
    vc = tmp_path / "vault" / "arqui"
    vc.mkdir(parents=True)
    (vc / "a.md").write_text("a")
    dest_obs = tmp_path / "Drive" / "ArqSoft" / "notas" / ".obsidian"
    dest_obs.mkdir(parents=True)
    (dest_obs / "keep").write_text("k")
    sync.mirror_vault(vc, tmp_path / "Drive" / "ArqSoft")
    assert (dest_obs / "keep").exists()


def test_mirror_vault_missing_source_raises(tmp_path):
    drive_course = tmp_path / "Drive" / "ArqSoft"
    (drive_course / "notas").mkdir(parents=True)
    (drive_course / "notas" / "precious.md").write_text("p")
    with pytest.raises(RuntimeError):
        sync.mirror_vault(tmp_path / "vault" / "nope", drive_course)
    assert (drive_course / "notas" / "precious.md").exists()
