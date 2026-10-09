from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import webvtt


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _secs(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def hms(t: float) -> str:
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def parse(path: Path) -> list[Cue]:
    cues: list[Cue] = []
    for c in webvtt.read(str(path)):
        text = re.sub(r"\s+", " ", c.text.replace("\n", " ")).strip()
        if not text:
            continue
        if cues and cues[-1].text == text:  # Vimeo repeats the same caption across adjacent cues
            cues[-1].end = max(cues[-1].end, _secs(c.end))
            continue
        cues.append(Cue(_secs(c.start), _secs(c.end), text))
    return cues


def load_glossary(path: Path | None) -> dict[str, str]:
    """Lines `wrong => right`; `#` starts a comment."""
    if not path or not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=>" in line:
            a, b = (x.strip() for x in line.split("=>", 1))
            out[a] = b
    return out


def apply_glossary(text: str, glossary: dict[str, str]) -> str:
    for wrong, right in glossary.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    return text


def paragraphs(cues: list[Cue], every: float = 30.0) -> list[tuple[float, str]]:
    """Group cues into paragraphs; a cue starting >= `every` s after the paragraph start opens a new one."""
    out: list[tuple[float, str]] = []
    buf: list[str] = []
    start: float | None = None
    for c in cues:
        if start is not None and c.start - start >= every:
            out.append((start, " ".join(buf)))
            buf, start = [], None
        if start is None:
            start = c.start
        buf.append(c.text)
    if buf and start is not None:
        out.append((start, " ".join(buf)))
    return out


def to_markdown(cues: list[Cue], title: str, every: float = 30.0, glossary: dict[str, str] | None = None) -> str:
    lines = [f"# Transcript · {title}", ""]
    for t, text in paragraphs(cues, every):
        lines.append(f"[{hms(t)}] {apply_glossary(text, glossary or {})}")
    return "\n".join(lines) + "\n"


def convert(vtt_path: Path, out_path: Path, title: str, every: float = 30.0, glossary_path: Path | None = None) -> int:
    cues = parse(vtt_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_markdown(cues, title, every, load_glossary(glossary_path)), encoding="utf-8")
    return len(cues)
