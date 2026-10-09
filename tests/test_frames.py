import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pipeline import frames


def img(path: Path, color, text: str = ""):
    im = Image.new("RGB", (320, 180), color)
    if text:
        ImageDraw.Draw(im).text((10, 10), text, fill="black")
    im.save(path)
    return path


def test_segments_collapse_identical_consecutive(tmp_path):
    files = [img(tmp_path / f"{i:05d}.jpg", "white", "slide A") for i in range(3)]
    files += [img(tmp_path / f"{i:05d}.jpg", (20, 20, 20), "") for i in range(3, 5)]
    segs = frames.segments(files, every=10, same_dist=6)
    assert [(s.t, s.t_end) for s in segs] == [(0.0, 30.0), (30.0, 50.0)]


def test_global_dups_marked(tmp_path):
    a = img(tmp_path / "a.jpg", "white", "slide A")
    b = img(tmp_path / "b.jpg", (20, 20, 20))
    a2 = img(tmp_path / "c.jpg", "white", "slide A")
    segs = frames.segments([a, b, a2], every=10, same_dist=6)
    frames.mark_global_dups(segs, same_dist=6)
    assert segs[2].dup_of == 0 and segs[1].dup_of is None


def test_decide_keep_rules():
    s = [frames.Segment(0, 0, 60, "f", "0" * 16, ocr="uno dos tres cuatro cinco"),
         frames.Segment(1, 60, 65, "f", "0" * 16, ocr="texto corto pero muchas palabras aqui"),
         frames.Segment(2, 65, 200, "f", "0" * 16, ocr="hola"),
         frames.Segment(3, 200, 300, "f", "0" * 16, ocr="a b c d e", dup_of=0)]
    frames.decide_keep(s, min_seconds=8)
    assert [x.keep for x in s] == [True, False, False, False]
    assert s[1].reason == "too_short" and s[2].reason == "no_text" and s[3].reason == "dup_of:0"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_sample_and_export_with_ffmpeg(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=25:size=320x180:rate=5",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    files = frames.sample(video, tmp_path / "sample", every=10)
    assert len(files) == 3
    segs = frames.segments(files, every=10, same_dist=6)
    for s in segs:
        s.keep = True
    out = frames.export(video, segs, tmp_path / "img", width=160)
    assert len(out) == len(segs) and all(p.exists() for p in out)
    frames.write_manifest(tmp_path / "frames.json", "c1", 10, segs)
    assert '"class_id": "c1"' in (tmp_path / "frames.json").read_text()
