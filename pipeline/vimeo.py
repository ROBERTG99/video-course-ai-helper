from __future__ import annotations

from dataclasses import dataclass

from curl_cffi import requests

VIEWER_URL = "https://vimeo.com/_next/viewer"


@dataclass(frozen=True)
class ShowcaseVideo:
    video_id: str
    title: str
    duration: int
    created_time: str  # ISO-8601 as returned by the API
    embed_url: str  # signed player URL; expires in ~24h, use it right away


class VimeoShowcase:
    """Password-protected showcase listing. Same flow yt-dlp's VimeoAlbumIE uses, but we keep player_embed_url."""

    def __init__(self, showcase_id: str, password: str, session=None):
        self.showcase_id, self.password = showcase_id, password
        self.s = session or requests.Session(impersonate="chrome")

    def _viewer(self) -> dict:
        r = self.s.get(VIEWER_URL, headers={"Accept": "application/json"})
        r.raise_for_status()
        return r.json()

    def _hashed_pass(self, xsrft: str) -> str:
        r = self.s.post(f"https://vimeo.com/showcase/{self.showcase_id}/auth",
                        data={"password": self.password, "token": xsrft},
                        headers={"X-Requested-With": "XMLHttpRequest"})
        if r.status_code == 401:
            raise PermissionError(f"wrong password for showcase {self.showcase_id}")
        r.raise_for_status()
        return r.json()["hashed_pass"]

    def list_videos(self) -> list[ShowcaseVideo]:
        v = self._viewer()
        hp = self._hashed_pass(v["xsrft"])
        out: list[ShowcaseVideo] = []
        page = 1
        while True:
            r = self.s.get(
                f"https://api.vimeo.com/albums/{self.showcase_id}/videos",
                params={"fields": "uri,name,player_embed_url,duration,created_time", "per_page": 100,
                        "page": page, "_hashed_pass": hp},
                headers={"Authorization": "jwt " + v["jwt"], "Accept": "application/json"},
            )
            r.raise_for_status()
            body = r.json()
            for d in body.get("data", []):
                out.append(ShowcaseVideo(d["uri"].rsplit("/", 1)[-1], d.get("name") or "",
                                         int(d.get("duration") or 0), d.get("created_time") or "",
                                         d["player_embed_url"]))
            if not (body.get("paging") or {}).get("next"):
                break
            page += 1
        return sorted(out, key=lambda x: x.created_time)
