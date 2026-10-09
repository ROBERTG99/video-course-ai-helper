from pipeline.vimeo import ShowcaseVideo, VimeoShowcase


class FakeResp:
    def __init__(self, status, body):
        self.status_code, self._b = status, body

    def json(self):
        return self._b

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(self.status_code)


class FakeSession:
    def __init__(self, pages, auth_status=200):
        self.pages, self.auth_status, self.calls = pages, auth_status, []

    def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url, params, headers))
        if url.endswith("/_next/viewer"):
            return FakeResp(200, {"jwt": "J", "xsrft": "X"})
        page = int((params or {}).get("page", 1))
        body = {"data": self.pages[page - 1], "paging": {"next": f"?page={page+1}" if page < len(self.pages) else None}}
        return FakeResp(200, body)

    def post(self, url, data=None, headers=None):
        self.calls.append(("POST", url, data, headers))
        return FakeResp(self.auth_status, {"hashed_pass": "HP"})


def vid(i, name, created):
    return {"uri": f"/users/1/albums/9/videos/{i}", "name": name, "duration": 100 + i,
            "created_time": created, "player_embed_url": f"https://player.vimeo.com/video/{i}?h=abc&s=sig_1"}


def test_list_videos_auths_pages_and_sorts():
    s = FakeSession([[vid(2, "B | 07-10-2026", "2026-10-08T06:00:00+00:00")], [vid(1, "A | 30-09-2026", "2026-10-01T06:00:00+00:00")]])
    out = VimeoShowcase("9", "pw", session=s).list_videos()
    assert [v.video_id for v in out] == ["1", "2"]
    assert out[0] == ShowcaseVideo("1", "A | 30-09-2026", 101, "2026-10-01T06:00:00+00:00", "https://player.vimeo.com/video/1?h=abc&s=sig_1")
    post = next(c for c in s.calls if c[0] == "POST")
    assert post[1] == "https://vimeo.com/showcase/9/auth" and post[2] == {"password": "pw", "token": "X"}
    listing = [c for c in s.calls if "/albums/9/videos" in c[1]]
    assert len(listing) == 2 and listing[0][3]["Authorization"] == "jwt J" and listing[0][2]["_hashed_pass"] == "HP"


def test_wrong_password():
    import pytest
    with pytest.raises(PermissionError):
        VimeoShowcase("9", "bad", session=FakeSession([[]], auth_status=401)).list_videos()
