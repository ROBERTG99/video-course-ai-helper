from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def _move_into(src: Path, target: Path) -> None:
    """Move src to target without deleting anything already at target.

    Same-size existing file: it is already backed up, so just drop the source.
    Different size: overwrite via copy2, then drop the source.
    """
    if src.is_dir():
        target.mkdir(parents=True, exist_ok=True)
        for child in list(src.iterdir()):
            _move_into(child, target / child.name)
        src.rmdir()
        return
    if target.is_file() and target.stat().st_size == src.stat().st_size:
        src.unlink()
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, target)
    src.unlink()


def move_raw(raw_dir: Path, dump_root: Path, course: str, class_id: str) -> Path:
    dest = dump_root / course / class_id
    dest.mkdir(parents=True, exist_ok=True)
    for p in list(raw_dir.iterdir()):
        _move_into(p, dest / p.name)
    return dest


def mirror_vault(vault_course: Path, drive_course_dir: Path) -> None:
    if not vault_course.is_dir():
        raise RuntimeError(f"vault course dir not found: {vault_course} (refusing to mirror)")
    dest = drive_course_dir / "notas"
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["rsync", "-a", "--delete", "--exclude", ".obsidian", "--exclude", ".DS_Store",
         f"{vault_course}/", f"{dest}/"],
        check=True, capture_output=True,
    )


def repoint_video(note: Path, video: Path) -> bool:
    """After the raw media moved to the Drive dump, point the note's `video_path` frontmatter at it."""
    if not note.exists() or not video.exists():
        return False
    text = note.read_text(encoding="utf-8")
    new = re.sub(r"^video_path: .*$", f"video_path: {video}", text, count=1, flags=re.MULTILINE)
    if new != text:
        note.write_text(new, encoding="utf-8")
    return new != text


ROOT_NOTES = ("00-MOC-2026.md", "calendario.md")


def copy_root_notes(vault: Path, drive_root: Path) -> list[Path]:
    """Copy the vault-level notes (year MOC, calendario) to the Drive root. Returns the copied targets."""
    out: list[Path] = []
    for name in ROOT_NOTES:
        src = vault / name
        if src.exists():
            shutil.copy2(src, drive_root / name)
            out.append(drive_root / name)
    return out
