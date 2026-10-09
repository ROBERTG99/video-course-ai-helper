from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import imagehash
from PIL import Image


@dataclass
class Segment:
    idx: int
    t: float
    t_end: float
    file: str
    phash: str
    ocr: str = ""
    keep: bool = False
    reason: str = ""
    dup_of: int | None = None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def sample(video: Path, out_dir: Path, every: int, width: int = 640) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
          "-vf", f"fps=1/{every},scale={width}:-2", "-q:v", "4", str(out_dir / "%05d.jpg")])
    return sorted(out_dir.glob("*.jpg"))


def phash(path: Path) -> imagehash.ImageHash:
    with Image.open(path) as im:
        return imagehash.phash(im)


def segments(files: list[Path], every: int, same_dist: int) -> list[Segment]:
    """Collapse runs of visually identical consecutive frames into one segment each."""
    segs: list[Segment] = []
    prev = None
    for i, f in enumerate(files):
        h = phash(f)
        t = float(i * every)
        if prev is not None and (h - prev) <= same_dist:
            segs[-1].t_end = t + every
            continue
        segs.append(Segment(len(segs), t, t + every, str(f), str(h)))
        prev = h
    return segs


def mark_global_dups(segs: list[Segment], same_dist: int) -> None:
    """The professor goes back to an earlier slide: keep one image, point the rest at it."""
    kept: list[tuple[int, imagehash.ImageHash]] = []
    for s in segs:
        h = imagehash.hex_to_hash(s.phash)
        for idx, kh in kept:
            if (h - kh) <= same_dist:
                s.dup_of = idx
                break
        else:
            kept.append((s.idx, h))


def decide_keep(segs: list[Segment], min_seconds: float, min_words: int = 4) -> None:
    for s in segs:
        words = len(s.ocr.split())
        if s.dup_of is not None:
            s.keep, s.reason = False, f"dup_of:{s.dup_of}"
        elif s.t_end - s.t < min_seconds:
            s.keep, s.reason = False, "too_short"
        elif words < min_words:
            s.keep, s.reason = False, "no_text"
        else:
            s.keep, s.reason = True, f"text:{words}w"


def export(video: Path, segs: list[Segment], out_dir: Path, width: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for s in segs:
        if not s.keep:
            continue
        dest = out_dir / f"{s.idx:04d}.jpg"
        # Last segment's nominal t_end can overshoot the video: fall back to its start.
        for ts in ((s.t + s.t_end) / 2, s.t):
            dest.unlink(missing_ok=True)
            try:
                _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{ts:.2f}", "-i", str(video),
                      "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)])
            except subprocess.CalledProcessError:
                continue
            if dest.exists():
                break
        else:
            raise RuntimeError(f"ffmpeg could not export a frame for segment {s.idx} (t={s.t}..{s.t_end})")
        s.file = str(dest)
        out.append(dest)
    return out


def write_manifest(path: Path, class_id: str, every: int, segs: list[Segment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"class_id": class_id, "sample_every": every, "frames": [asdict(s) for s in segs]},
                               ensure_ascii=False, indent=1), encoding="utf-8")


def process(video: Path, work_dir: Path, img_dir: Path, class_id: str, cfg: dict, ocr_fn=None) -> list[Segment]:
    """Full pass: sample -> segments -> OCR -> dedupe -> keep -> export -> frames.json."""
    from .ocr import ocr_segments

    every, dist = int(cfg["sample_every_seconds"]), int(cfg["phash_distance_same"])
    files = sample(video, work_dir / "sample", every)
    segs = segments(files, every, dist)
    (ocr_fn or ocr_segments)(segs)
    mark_global_dups(segs, dist)
    decide_keep(segs, float(cfg["min_slide_seconds"]))
    export(video, segs, img_dir, int(cfg["export_width"]))
    write_manifest(work_dir / "frames.json", class_id, every, segs)
    return segs
