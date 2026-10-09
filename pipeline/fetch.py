from __future__ import annotations

from pathlib import Path

import yt_dlp

from . import config, state
from .config import Course
from .naming import assign_ids
from .vimeo import ShowcaseVideo, VimeoShowcase

PREFERRED_VTT = "video.es-x-autogen.vtt"


def ydl_opts(dest: Path, subs_only: bool, max_height: int = 720) -> dict:
    return {
        "outtmpl": str(dest / "video.%(ext)s"),
        "format": f"bv*[height<={max_height}]+ba/b[height<={max_height}]/b",
        "merge_output_format": "mp4",
        "writesubtitles": True,
        "subtitleslangs": ["all"],
        "subtitlesformat": "vtt",
        "writeinfojson": True,
        "skip_download": subs_only,
        "http_headers": {"Referer": "https://vimeo.com/"},
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "retries": 5,
    }


def pick_vtt(dest: Path) -> Path | None:
    """Prefers the official es-x-autogen track; otherwise the first VTT found."""
    preferred = dest / PREFERRED_VTT
    if preferred.exists():
        return preferred
    vtts = sorted(dest.glob("video.*.vtt"))
    return vtts[0] if vtts else None


def _store(p: Path) -> str:
    """Repo-relative path when under config.ROOT, absolute otherwise."""
    try:
        return str(p.relative_to(config.ROOT))
    except ValueError:
        return str(p)


def download(video: ShowcaseVideo, dest: Path, subs_only: bool) -> dict:
    """Downloads into dest. Returns {vtt, video, subs_langs}; vtt is None when Vimeo exposes no track."""
    dest.mkdir(parents=True, exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts(dest, subs_only)) as ydl:
        info = ydl.extract_info(video.embed_url, download=True)
    vtt = pick_vtt(dest)
    mp4 = dest / "video.mp4"
    return {
        "vtt": _store(vtt) if vtt else None,
        "video": _store(mp4) if mp4.exists() else None,
        "subs_langs": sorted((info.get("subtitles") or {}).keys()),
    }


def fetch_course(course: Course, subs_only: bool = False, only_class: str | None = None, force: bool = False) -> list[dict]:
    videos = VimeoShowcase(course.showcase_id, course.password).list_videos()
    ids = assign_ids(videos)
    results: list[dict] = []
    for v in videos:
        cid = ids[v.video_id]
        if only_class and cid != only_class:
            continue
        d = config.class_dirs(course.slug, cid)
        st = state.load(d["state"])
        prev = st.get("stages", {}).get("fetch", {})
        if prev.get("status") == "ok" and not force and (subs_only or prev.get("video")):
            results.append({"class_id": cid, "skipped": True})
            continue
        state.set_meta(d["state"], course=course.slug, class_id=cid, video_id=v.video_id, title=v.title,
                       duration=v.duration, created_time=v.created_time,
                       vimeo_url=f"https://vimeo.com/showcase/{course.showcase_id}/video/{v.video_id}")
        try:
            r = download(v, d["raw"], subs_only)
        except Exception as e:  # noqa: BLE001 - yt_dlp.utils.DownloadError and network errors: class stays blocked, loop continues
            msg = str(e)[:500]
            state.mark(d["state"], "fetch", "blocked", error=msg)
            results.append({"class_id": cid, "error": msg})
            continue
        if not r["vtt"]:
            state.mark(d["state"], "fetch", "blocked", error="sin VTT en Vimeo", **r)
        else:
            state.mark(d["state"], "fetch", "ok", **r)
        results.append({"class_id": cid, **r})
    return results
