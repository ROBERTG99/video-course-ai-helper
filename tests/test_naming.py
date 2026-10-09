from datetime import date

from pipeline.naming import assign_ids, class_date, class_id
from pipeline.vimeo import ShowcaseVideo


def test_date_from_title_dd_mm_yyyy():
    assert class_date("FI-3851-Arq | 07-10-2026", "2026-10-08T06:01:54+00:00") == date(2026, 10, 7)


def test_date_fallback_created_time():
    assert class_date("sin fecha", "2026-10-08T06:01:54+00:00") == date(2026, 10, 8)


def test_assign_ids_chronological():
    vids = [ShowcaseVideo("1", "x | 30-09-2026", 1, "2026-10-01T00:00:00+00:00", "u"),
            ShowcaseVideo("2", "y | 07-10-2026", 1, "2026-10-08T00:00:00+00:00", "u")]
    assert assign_ids(vids) == {"1": "2026-09-30-clase-01", "2": "2026-10-07-clase-02"}
    assert class_id(15, "z | 07-10-2026", "") == "2026-10-07-clase-15"
