from __future__ import annotations

import re
from pathlib import Path

T = r"\d{1,2}:\d{2}:\d{2}"
TOKEN = rf"\[{T}(?:[ \t]*(?:[-–—,;]|a|y)[ \t]*{T})*\]"
SEP = r"[ \t]*(?:[-–—,;/]|y|a|vs\.?)?[ \t]*"
SEQ = re.compile(rf"[ \t]*{TOKEN}(?:{SEP}{TOKEN})*(?!\()")
TS_ONE = re.compile(T)
LIST_ONLY = re.compile(r"^\s*(?:[-*+]|\d+\.|#+)?\s*$")


M = "\x00"  # marks where a timestamp sequence was removed, so cleanup only touches those spots
PREP = r"(?:en|desde|hasta|ver|de|a|entre)"


def _clean_line(orig: str, marked: str) -> str | None:
    """Tidy a line that lost timestamps; None means the line is now empty and must go."""
    indent = orig[: len(orig) - len(orig.lstrip())]
    s = indent + marked.strip()
    s = re.sub(rf"[ \t]*\([ \t]*{M}[ \t]*\)", M, s)  # "audio ([00:00:48]-[00:04:24])," -> "audio,"
    s = re.sub(rf"^(\s*(?:[-*+]|\d+\.))[ \t]*{M}[ \t]*[,;:]?[ \t]*", r"\1 ", s)
    s = re.sub(rf"^(\s*){M}[ \t]*[,;:]?[ \t]*", r"\1", s)
    s = re.sub(rf"[ \t]+{PREP}[ \t]*{M}[ \t]*(?=[.,;:)\]]|$)", M, s)  # "confirmado en [01:05:08]."
    s = re.sub(rf"[,;:]?[ \t]*{M}[ \t]*(?=[.,;:)\]]|$)", "", s)
    s = re.sub(rf"[ \t]*{M}[ \t]*", " ", s).rstrip()
    return None if LIST_ONLY.match(s) else s


def strip_count(text: str) -> tuple[str, int]:
    """Remove [hh:mm:ss] tokens, ranges and sequences outside frontmatter and fenced code. Returns (text, removed)."""
    lines = text.split("\n")
    out: list[str] = []
    removed = 0
    in_fm = bool(lines) and lines[0] == "---"
    fence = False
    for i, line in enumerate(lines):
        if in_fm:
            out.append(line)
            if i > 0 and line == "---":
                in_fm = False
            continue
        if re.match(r"^\s*(```|~~~)", line):
            fence = not fence
            out.append(line)
            continue
        if fence:
            out.append(line)
            continue
        n = sum(len(TS_ONE.findall(m.group(0))) for m in SEQ.finditer(line))
        if not n:
            out.append(line)
            continue
        removed += n
        cleaned = _clean_line(line, SEQ.sub(M, line))
        if cleaned is not None:
            out.append(cleaned)
    return "\n".join(out), removed


def strip_timestamps(text: str) -> str:
    return strip_count(text)[0]


def strip_file(path: Path) -> int:
    """Strip timestamps from a note in place (only rewritten if it changed). Returns timestamps removed."""
    text = path.read_text(encoding="utf-8")
    new, n = strip_count(text)
    if new != text:
        path.write_text(new, encoding="utf-8")
    return n


HEADING_LINK = re.compile(r"^(#{1,6} )(.*\[\[.*)$", re.MULTILINE)
LEAD_LINK = re.compile(r"^\[\[[^\]]+\]\]\s*[—–-]\s*")
WIKI_IN_HEADING = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")


def plain_headings(text: str) -> tuple[str, int]:
    """Headings must be plain text so `[[note#Heading]]` anchors work: `### [[slug]] — Title` -> `### Title`."""
    n = 0

    def repl(m: re.Match) -> str:
        nonlocal n
        n += 1
        body = LEAD_LINK.sub("", m.group(2))
        body = WIKI_IN_HEADING.sub(lambda w: w.group(2) or w.group(1).split("#")[-1], body)
        return m.group(1) + body.strip()

    return HEADING_LINK.sub(repl, text), n
