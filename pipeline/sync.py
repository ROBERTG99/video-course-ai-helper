from __future__ import annotations

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
