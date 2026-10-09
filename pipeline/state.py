from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

STAGES = ["fetch", "transcript", "frames", "analyze", "validate", "integrate", "sync"]


def load(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"stages": {}}


def save(path: Path, st: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")


def mark(path: Path, stage: str, status: str, **extra) -> dict:
    if stage not in STAGES:
        raise ValueError(f"unknown stage {stage!r}")
    if status not in ("ok", "blocked"):
        raise ValueError(f"unknown status {status!r}")
    st = load(path)
    st["stages"][stage] = {"status": status, "at": datetime.now(UTC).isoformat(timespec="seconds"), **extra}
    save(path, st)
    return st


def is_done(path: Path, stage: str) -> bool:
    return load(path).get("stages", {}).get(stage, {}).get("status") == "ok"


def set_meta(path: Path, **meta) -> dict:
    st = load(path)
    st.update(meta)
    save(path, st)
    return st


def next_pending(path: Path) -> str | None:
    for s in STAGES:
        if not is_done(path, s):
            return s
    return None


def all_states(state_root: Path, course: str) -> list[dict]:
    return [load(p) for p in sorted((state_root / course).glob("*.json"))]
