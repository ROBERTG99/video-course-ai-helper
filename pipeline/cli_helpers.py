from __future__ import annotations

import json
from pathlib import Path

from . import config, state

PREV = {s: (state.STAGES[i - 1] if i else None) for i, s in enumerate(state.STAGES)}


def pending_classes(course: str, stage: str, force: bool = False) -> list[str]:
    """Class ids whose previous stage is ok and this stage is not ok (or all with prev ok when force)."""
    out: list[str] = []
    for p in sorted((config.STATE / course).glob("*.json")):
        prev = PREV[stage]
        if prev and not state.is_done(p, prev):
            continue
        if state.is_done(p, stage) and not force:
            continue
        out.append(p.stem)
    return out


def meta_for(course: config.Course, class_id: str) -> dict:
    d = config.class_dirs(course.slug, class_id)
    st = state.load(d["state"])
    video = st.get("stages", {}).get("fetch", {}).get("video")
    return {
        "curso": course.slug, "nombre_curso": course.full_name, "class_id": class_id,
        "fecha": class_id[:10], "numero": int(class_id[-2:]), "titulo": st.get("title", ""),
        "duracion": round((st.get("duration") or 0) / 60), "vimeo_url": st.get("vimeo_url", ""),
        "video_path": video or "—", "img_rel": f"img/{class_id}",
    }


def relpath(p: Path) -> str:
    try:
        return str(p.relative_to(config.ROOT))
    except ValueError:
        return str(p)


def resolve_path(p: str) -> Path:
    """State stores paths relative to ROOT; absolute paths are kept as-is."""
    path = Path(p)
    return path if path.is_absolute() else config.ROOT / path


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))
