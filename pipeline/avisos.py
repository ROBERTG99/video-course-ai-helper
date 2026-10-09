from __future__ import annotations

import re
from pathlib import Path

from .vtt import hms

LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] (.*)$")


def read_transcript(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE.match(line)
        if m:
            h, mi, s, text = m.groups()
            out.append((int(h) * 3600 + int(mi) * 60 + int(s), text))
    return out


def excerpts(paras: list[tuple[int, str]], keywords: list[str], context: int = 60) -> list[dict]:
    pat = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    hits: list[dict] = []
    for t, text in paras:
        found = sorted({m.group(0).lower() for m in pat.finditer(text)})
        if not found:
            continue
        ctx = [p for p in paras if t - context <= p[0] <= t + context]
        hits.append({"t": t, "keywords": found, "text": " ".join(x[1] for x in ctx)})
    return hits


def to_markdown(hits: list[dict]) -> str:
    lines = ["# Fragmentos con keywords de avisos", ""]
    for h in hits:
        lines.append(f"## [{hms(h['t'])}] {', '.join(h['keywords'])}\n{h['text']}\n")
    return "\n".join(lines)
