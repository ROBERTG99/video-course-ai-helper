import json

from pipeline import prompt_builder as pb


def test_frames_table_only_kept(tmp_path):
    m = tmp_path / "frames.json"
    m.write_text(json.dumps({"class_id": "c", "sample_every": 10, "frames": [
        {"idx": 1, "t": 10, "t_end": 70, "file": "/x/img/0001.jpg", "phash": "", "ocr": "Capas | logica",
         "keep": True, "reason": "", "dup_of": None},
        {"idx": 2, "t": 70, "t_end": 80, "file": "/x/s.jpg", "phash": "", "ocr": "",
         "keep": False, "reason": "", "dup_of": None}]}))
    table = pb.frames_table(m)
    assert "0001.jpg" in table and "s.jpg" not in table and "00:00:10–00:01:10" in table and "Capas / logica" in table


def test_build_prompt_has_all_blocks(tmp_path, repo_root):
    m = tmp_path / "frames.json"
    m.write_text(json.dumps({"class_id": "c", "sample_every": 10, "frames": []}))
    t = tmp_path / "transcript.md"
    t.write_text("# Transcript · c\n\n[00:00:00] hola\n")
    meta = {"curso": "arqui", "class_id": "c"}
    out = pb.build_analysis_prompt(meta, t, m, tmp_path / "c.md", tmp_path / "temas.json", "img/c")
    for needle in ("## Metadatos", '"curso": "arqui"', "## Salidas obligatorias", "## Plantilla de la nota",
                   "## Frames disponibles", "## Transcript", "[00:00:00] hola", "![](img/c/<archivo>)",
                   "## Resumen ejecutivo"):
        assert needle in out
    assert out.startswith((repo_root / "prompts" / "analista-clase.md").read_text(encoding="utf-8")[:40])


def test_build_avisos_prompt(tmp_path, monkeypatch):
    prompts = tmp_path / "prompts"
    prompts.mkdir()
    (prompts / "verificador-avisos.md").write_text("# Rol: verificador de avisos\n", encoding="utf-8")
    monkeypatch.setattr(pb, "PROMPTS", prompts)
    exc = tmp_path / "excerpts.md"
    exc.write_text("# Fragmentos con keywords de avisos\n\n## [00:00:30] parcial\nel parcial es el quince\n",
                   encoding="utf-8")
    meta = {"curso": "arqui", "class_id": "c"}
    out = pb.build_avisos_prompt(meta, exc, tmp_path / "nota.md", tmp_path / "review.md")
    assert out.startswith("# Rol: verificador de avisos")
    for needle in ('"curso": "arqui"', str(tmp_path / "nota.md"), str(tmp_path / "review.md"),
                   "el parcial es el quince"):
        assert needle in out


def test_existing_temas_listed(tmp_path):
    m = tmp_path / "frames.json"
    m.write_text(json.dumps({"class_id": "c", "sample_every": 10, "frames": []}))
    t = tmp_path / "transcript.md"
    t.write_text("[00:00:00] hola\n")
    out = pb.build_analysis_prompt({"curso": "arqui"}, t, m, tmp_path / "c.md", tmp_path / "t.json", "img/c",
                                   [("adr", "ADR")])
    assert "## Temas ya existentes en el curso" in out and "- `adr` — ADR" in out
    assert out.index("## Temas ya existentes") < out.index("## Transcript")
