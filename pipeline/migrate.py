from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import config

CLASS_ID = re.compile(r"^\d{4}-\d{2}-\d{2}-clase-\d{2}$")


@dataclass
class RenameReport:
    renamed: int = 0
    links: int = 0
    files: int = 0


def course_class_ids(slug: str, state_dir: Path, vault_course: Path) -> list[str]:
    """Class ids of a course: state/<c>/*.json plus bare-named notes still in vault/<c>/clases/."""
    ids = {p.stem for p in state_dir.glob("*.json")}
    ids |= {p.stem for p in (vault_course / "clases").glob("*.md")}
    ids |= {p.stem.removeprefix(f"{slug}-") for p in (vault_course / "clases").glob(f"{slug}-*.md")}
    return sorted(i for i in ids if CLASS_ID.match(i))


def _link_pattern(class_ids: list[str]) -> re.Pattern | None:
    if not class_ids:
        return None
    alt = "|".join(re.escape(c) for c in sorted(class_ids, key=len, reverse=True))
    # `[[<id>` followed by `]`, `|`, `\|` (inside tables) or `#`; an already-prefixed `[[<c>-<id>` never matches
    return re.compile(rf"(!?\[\[)({alt})(?=[\]|#\\])")


def _rewrite(path: Path, pat: re.Pattern, prefix: str, rep: RenameReport) -> None:
    text = path.read_text(encoding="utf-8")
    new, n = pat.subn(lambda m: f"{m.group(1)}{prefix}{m.group(2)}", text)
    if n:
        path.write_text(new, encoding="utf-8")
        rep.links += n
        rep.files += 1


def rename_notes(slug: str, vault: Path | None = None, work: Path | None = None,
                 state: Path | None = None) -> RenameReport:
    """Rename vault/<c>/clases/<class_id>.md -> <c>-<class_id>.md and rewrite wikilinks to them in vault/<c>/,
    work/<c>/temas/ and the vault/calendario.md rows of the course. Idempotent."""
    vault, work, state = vault or config.VAULT, work or config.WORK, state or config.STATE
    vc = vault / slug
    rep = RenameReport()
    ids = course_class_ids(slug, state / slug, vc)
    for cid in ids:
        old, new = vc / "clases" / f"{cid}.md", vc / "clases" / f"{config.note_name(slug, cid)}.md"
        if old.exists() and not new.exists():
            old.rename(new)
            rep.renamed += 1
    pat = _link_pattern(ids)
    if pat is None:
        return rep
    prefix = f"{slug}-"
    files = sorted(vc.rglob("*.md")) + sorted((work / slug / "temas").glob("*.md"))
    for p in files:
        _rewrite(p, pat, prefix, rep)
    cal = vault / "calendario.md"
    if cal.exists():
        row = re.compile(rf"^(\|\s*{re.escape(slug)}\s*\|\s*)(.*)$", re.MULTILINE)
        text = cal.read_text(encoding="utf-8")
        n_total = 0

        def fix_row(m: re.Match) -> str:
            nonlocal n_total
            rest, n = pat.subn(lambda w: f"{w.group(1)}{prefix}{w.group(2)}", m.group(2), count=1)
            n_total += n
            return m.group(1) + rest

        new = row.sub(fix_row, text)
        if n_total:
            cal.write_text(new, encoding="utf-8")
            rep.links += n_total
            rep.files += 1
    return rep
