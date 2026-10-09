from __future__ import annotations

import re
from datetime import date

DATE_IN_TITLE = re.compile(r"(\d{2})-(\d{2})-(\d{4})\s*$")


def class_date(title: str, created_time: str) -> date:
    m = DATE_IN_TITLE.search(title or "")
    if m:
        d, mo, y = map(int, m.groups())
        return date(y, mo, d)
    return date.fromisoformat(created_time[:10])


def class_id(ordinal: int, title: str, created_time: str) -> str:
    return f"{class_date(title, created_time).isoformat()}-clase-{ordinal:02d}"


def assign_ids(videos) -> dict[str, str]:
    """video_id -> class_id. `videos` must already be sorted chronologically (VimeoShowcase does it)."""
    return {v.video_id: class_id(i + 1, v.title, v.created_time) for i, v in enumerate(videos)}
