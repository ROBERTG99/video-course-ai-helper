import pytest

from pipeline import config


def test_load_settings_reads_courses_and_env(repo_root, tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ARQUI_VIMEO_URL=https://vimeo.com/showcase/123\nARQUI_VIMEO_PASSWORD=x\nDRIVE_ROOT=/tmp/drive\n")
    for k in ("ARQUI_VIMEO_URL", "ARQUI_VIMEO_PASSWORD", "DRIVE_ROOT"):
        monkeypatch.delenv(k, raising=False)
    s = config.load_settings(repo_root, env_file=env)
    assert set(s.courses) == {"arqui", "negsoft", "dbpt", "isa2"}
    c = config.course(s, "arqui")
    assert c.showcase_id == "123" and c.drive_folder == "ArqSoft"
    assert s.drive_root.name == "drive"
    assert "parcial" in s.avisos_keywords


def test_course_without_credentials_raises(repo_root, tmp_path, monkeypatch):
    for k in ("DBPT_VIMEO_URL", "DBPT_VIMEO_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    s = config.load_settings(repo_root, env_file=tmp_path / "empty.env")
    with pytest.raises(RuntimeError):
        config.course(s, "dbpt")


def test_class_dirs_layout():
    d = config.class_dirs("arqui", "2026-10-07-clase-15")
    assert d["raw"].as_posix().endswith("raw/arqui/2026-10-07-clase-15")
    assert d["note"].name == "arqui-2026-10-07-clase-15.md"
    assert config.note_name("isa2", "2026-10-07-clase-15") == "isa2-2026-10-07-clase-15"
    assert d["img"].as_posix().endswith("vault/arqui/clases/img/2026-10-07-clase-15")
