# Video Course AI Helper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Playbook de Robert manda:** máx. **4 agentes simultáneos**, `model: sonnet` para implementar, `opus` solo para verificar; el contexto de cada tarea viaja en el prompt (pegar la tarea completa + la sección "Contratos"); checkpoint en `_meta/PROGRESS.md` al cerrar cada ola.

**Goal:** Un pipeline reproducible que, por curso, baja cada grabación de Vimeo con su VTT, extrae frames clave, genera con Claude una nota de clase completa (con avisos del profesor verificados) y la integra a un vault Obsidian espejado a Drive.

**Architecture:** Módulos Python pequeños con una responsabilidad (`pipeline/*.py`) orquestados por un CLI `typer` idempotente con estado por clase (`state/<curso>/<clase>.json`). Los pasos LLM reciben un prompt armado por script y escriben archivos con contrato fijo; nada LLM es necesario para los tests. Resultados (`vault/`, `raw/`, `work/`, `state/`) nunca entran a git.

**Tech Stack:** Python 3.12 (uv), yt-dlp + curl_cffi, ffmpeg, imagehash/Pillow, tesseract (`spa+eng`), webvtt-py, typer, pytest, ruff, Claude Code (agentes en sesión y `claude -p`).

---

## 0. Contratos (leer antes de cualquier tarea; ningún agente los cambia sin decisión en `_meta/DECISIONES.md`)

### 0.1 Rutas
| Qué | Dónde |
|---|---|
| Crudo por clase | `raw/<curso>/<class_id>/{video.mp4, video.<lang>.vtt, video.info.json}` |
| Intermedio | `work/<curso>/<class_id>/{transcript.md, sample/, frames.json, analysis-prompt.md, avisos-excerpts.md, temas-candidatos.json, avisos-review.md, run.json}` |
| Estado | `state/<curso>/<class_id>.json` |
| Vault | `vault/<curso>/clases/<class_id>.md`, `vault/<curso>/clases/img/<class_id>/NNNN.jpg`, `vault/<curso>/temas/<slug>.md`, `vault/<curso>/MOC-<curso>.md`, `vault/<curso>/MOC-<curso>.canvas`, `vault/<curso>/avisos-<curso>.md`, `vault/00-MOC-2026.md`, `vault/calendario.md` |
| Drive | `$DRIVE_ROOT/<drive_folder>/notas/` (espejo de `vault/<curso>/`), `$DRIVE_ROOT/_clases-dump/<curso>/<class_id>/` (crudo) |
| Cursos | `config/courses.yaml` (slug, full_name, drive_folder, env_prefix) + `.env` (`<PREFIX>_VIMEO_URL`, `<PREFIX>_VIMEO_PASSWORD`, `DRIVE_ROOT`) |

`class_id` = `YYYY-MM-DD-clase-NN`: fecha = `dd-mm-yyyy` al final del título de Vimeo (ej. `... | 07-10-2026`), si no hay, fecha de `created_time`; `NN` = orden cronológico 1-based dentro del curso.

### 0.2 Retrieval (verificado 2026-10-09)
1. `GET https://vimeo.com/_next/viewer` → `{jwt, xsrft}` (sesión `curl_cffi` impersonando Chrome).
2. `POST https://vimeo.com/showcase/<id>/auth` form `{password, token: xsrft}` header `X-Requested-With: XMLHttpRequest` → `{hashed_pass}`; 401 = password incorrecto.
3. `GET https://api.vimeo.com/albums/<id>/videos?fields=uri,name,player_embed_url,duration,created_time&per_page=100&page=N&_hashed_pass=<hp>` header `Authorization: jwt <jwt>` → `data[]`. `player_embed_url` es `https://player.vimeo.com/video/<vid>?bypass_privacy=1&context=...&h=<hash>&s=<sig>_<epoch>` y **expira** (~24 h): listar y bajar en la misma corrida.
4. `yt-dlp` sobre esa `player_embed_url` con `Referer: https://vimeo.com/` usa la ruta del player (sin login) y expone subtítulos `es-x-autogen` (vtt). El API client `web` de yt-dlp exige login: NO usar URLs `vimeo.com/showcase/.../video/...` directamente.
5. Sin track `es-x-autogen` ni otro `.vtt` → estado `fetch: blocked, error: "sin VTT en Vimeo"`. No hay ASR local.

### 0.3 `state/<curso>/<class_id>.json`
```json
{"course":"arqui","class_id":"2026-10-07-clase-15","video_id":"1233961388","title":"FI-3851-... | 07-10-2026","duration":7010,"created_time":"2026-10-08T06:01:54+00:00",
 "stages":{"fetch":{"status":"ok","at":"2026-10-09T18:00:00+00:00","vtt":"raw/arqui/2026-10-07-clase-15/video.es-x-autogen.vtt","video":"raw/.../video.mp4","subs_langs":["es-x-autogen"]},
           "transcript":{"status":"ok","at":"...","cues":1832},
           "frames":{"status":"ok","at":"...","segments":140,"kept":38},
           "analyze":{"status":"ok","at":"...","runner":"agent","cost_usd":0.41},
           "validate":{"status":"ok","at":"...","errors":[]},
           "integrate":{"status":"ok","at":"...","created":5,"updated":3},
           "sync":{"status":"ok","at":"..."}}}
```
`status` ∈ `ok | blocked`. Etapas en orden: fetch → transcript → frames → analyze → validate → integrate → sync. Una etapa `ok` no se re-corre sin `--force`.

### 0.4 `work/.../transcript.md`
```
# Transcript · arqui · 2026-10-07-clase-15

[00:00:00] texto del primer bloque de ~30 s …
[00:00:31] siguiente bloque …
```
Un párrafo por ~30 s (`transcript.paragraph_seconds`), glosario del curso aplicado (`config/glossary-<curso>.txt`, líneas `mal => bien`).

### 0.5 `work/.../frames.json`
```json
{"class_id":"2026-10-07-clase-15","sample_every":10,
 "frames":[{"idx":12,"t":120.0,"t_end":190.0,"file":"vault/arqui/clases/img/2026-10-07-clase-15/0012.jpg","phash":"c3f0…","ocr":"Arquitectura en capas …","keep":true,"reason":"text:41w","dup_of":null},
           {"idx":13,"t":190.0,"t_end":200.0,"file":"work/.../sample/00020.jpg","phash":"…","ocr":"","keep":false,"reason":"no_text","dup_of":null}]}
```

### 0.6 `work/.../temas-candidatos.json` (lo escribe el analista)
```json
[{"slug":"arquitectura-en-capas","titulo":"Arquitectura en capas","resumen":"≤5 líneas…","timestamps":["00:12:30","01:02:10"],"relacionados":["Acoplamiento y cohesión"]}]
```

### 0.7 Nota de clase (`templates/clase.md`)
Frontmatter obligatorio: `curso, fecha, numero, titulo, duracion, vimeo_url, video_path, estado, tags`. Secciones H2 en este orden exacto: `Resumen ejecutivo` · `⚠️ Avisos del profesor` · `Índice de temas` · `Desarrollo por tema` · `Conceptos y definiciones` · `Ejemplos, demos y código` · `Preguntas de alumnos y respuestas` · `Dudas / a verificar` · `Citas textuales relevantes` · `Material referenciado`. Imágenes: `![](img/<class_id>/0012.jpg)`. Notas: `[[slug]]`. Afirmaciones importantes con `[hh:mm:ss]`. Sección vacía = `—`.

### 0.8 CLI (`uv run python -m pipeline …`)
`list-showcase --course X` · `fetch --course X [--class ID] [--subs-only] [--force]` · `transcript --course X [--class ID]` · `frames --course X [--class ID]` · `prompt --course X --class ID` · `analyze --course X --class ID --runner agent|claude-p` · `validate --course X [--class ID]` · `integrate --course X` · `canvas --course X` · `sync --course X [--class ID]` · `status [--course X]` · `init-vault`.
Sin `--class`: itera todas las clases con la etapa anterior `ok` y la actual pendiente.

### 0.9 Reglas para agentes en paralelo
- Cada tarea lista **sus** archivos; un agente no toca archivos de otra tarea. `pipeline/__main__.py` y `pyproject.toml` solo se editan en las tareas que los nombran.
- Antes de commitear: `uv run ruff check pipeline tests` limpio y `uv run pytest -q` verde. Commit solo con los archivos de la tarea (`git add <paths>`; nunca `.`/`-A`).
- Respuesta del agente: rutas + resumen ≤3 líneas + `OK`/`BLOQUEADO <error>`.
- Una tarea bloqueada se reintenta UNA vez; si vuelve a fallar se reporta y se sigue con las demás.

### 0.10 Olas de ejecución (DoD de ola = todos sus commits en `master`, tests verdes, PROGRESS.md actualizado)
| Ola | Tareas (paralelas) | Agentes |
|---|---|---|
| 0 | T1 scaffolding | 1 (secuencial) |
| 1 | T2 vimeo+naming · T3 vtt · T4 frames+ocr · T5 note_validate | 4 |
| 2 | T6 fetch · T7 avisos+prompt_builder+runner · T8 integrate+canvas · T9 sync | 4 |
| 3 | T10 CLI · T11 prompts+agentes+skills | 2 |
| 4 | T12 pilot (1 clase arqui, con Robert) → T13 tandas · T14 rutina `/nueva-clase` | 1 + hasta 4 |

---

## Ola 0

### Task 1: Scaffolding del proyecto (uv, config, state, tests)

**Files:**
- Create: `pyproject.toml`, `.python-version`, `pipeline/__init__.py`, `pipeline/config.py`, `pipeline/state.py`, `tests/__init__.py`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_state.py`
- Modify: `config/courses.yaml` (sin cambios de contenido salvo si falta `env_prefix`)

**DoD:** `uv sync` ok · `uv run pytest -q` verde (4+ tests) · `uv run ruff check` limpio · `ffmpeg -version` y `tesseract --list-langs` incluyen `spa`.
**Deliverable:** entorno reproducible + carga de config/.env + estado por clase.

- [ ] **Step 1: pyproject + python pin**

```toml
# pyproject.toml
[project]
name = "video-course-ai-helper"
version = "0.1.0"
description = "Vimeo class recordings -> transcript, key frames, AI notes, Obsidian vault"
requires-python = ">=3.12,<3.13"
dependencies = [
  "yt-dlp[default,curl-cffi]>=2026.8.19",
  "curl_cffi>=0.10",
  "imagehash>=4.3",
  "pillow>=10",
  "pytesseract>=0.3.13",
  "webvtt-py>=0.5",
  "pyyaml>=6",
  "typer>=0.15",
  "rich>=13",
  "python-dotenv>=1.0",
]

[dependency-groups]
dev = ["pytest>=8", "ruff>=0.6"]

[tool.ruff]
line-length = 110
target-version = "py312"

[tool.pytest.ini_options]
testpaths = ["tests"]
```
Run: `uv python pin 3.12 && uv sync` · Expected: `.venv` creado, sin errores.

- [ ] **Step 2: tests de config (fallan)**

```python
# tests/conftest.py
import pytest
from pathlib import Path

@pytest.fixture
def repo_root() -> Path:
    return Path(__file__).resolve().parent.parent

# tests/test_config.py
import pytest
from pipeline import config

def test_load_settings_reads_courses_and_env(repo_root, tmp_path, monkeypatch):
    env = tmp_path / ".env"
    env.write_text("ARQUI_VIMEO_URL=https://vimeo.com/showcase/123\nARQUI_VIMEO_PASSWORD=x\nDRIVE_ROOT=/tmp/drive\n")
    for k in ("ARQUI_VIMEO_URL", "ARQUI_VIMEO_PASSWORD", "DRIVE_ROOT"):
        monkeypatch.delenv(k, raising=False)
    s = config.load_settings(repo_root, env_file=env)
    assert set(s.courses) == {"arqui", "negsoft", "dbpt", "isa2"}
    c = config.course(s, "arqui")
    assert c.showcase_id == "123" and c.drive_folder == "ArqSoft"
    assert s.drive_root.name == "drive"
    assert "parcial" in s.avisos_keywords

def test_course_without_credentials_raises(repo_root, tmp_path, monkeypatch):
    for k in ("DBPT_VIMEO_URL", "DBPT_VIMEO_PASSWORD"):
        monkeypatch.delenv(k, raising=False)
    s = config.load_settings(repo_root, env_file=tmp_path / "empty.env")
    with pytest.raises(RuntimeError):
        config.course(s, "dbpt")

def test_class_dirs_layout():
    d = config.class_dirs("arqui", "2026-10-07-clase-15")
    assert d["raw"].as_posix().endswith("raw/arqui/2026-10-07-clase-15")
    assert d["note"].name == "2026-10-07-clase-15.md"
    assert d["img"].as_posix().endswith("vault/arqui/clases/img/2026-10-07-clase-15")
```
Run: `uv run pytest tests/test_config.py -q` · Expected: FAIL `ModuleNotFoundError: pipeline.config`.

- [ ] **Step 3: config.py**

```python
# pipeline/config.py
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
RAW, STATE, WORK, VAULT = ROOT / "raw", ROOT / "state", ROOT / "work", ROOT / "vault"
TEMPLATES, PROMPTS, CONFIG = ROOT / "templates", ROOT / "prompts", ROOT / "config"


@dataclass(frozen=True)
class Course:
    slug: str
    full_name: str
    drive_folder: str
    showcase_url: str
    password: str

    @property
    def showcase_id(self) -> str:
        return self.showcase_url.rstrip("/").rsplit("/", 1)[-1]


@dataclass(frozen=True)
class Settings:
    courses: dict[str, Course]
    frames: dict
    transcript: dict
    avisos_keywords: list[str]
    drive_root: Path


def load_settings(root: Path = ROOT, env_file: Path | None = None) -> Settings:
    load_dotenv(env_file or root / ".env", override=True)
    cfg = yaml.safe_load((root / "config" / "courses.yaml").read_text(encoding="utf-8"))
    courses: dict[str, Course] = {}
    for slug, c in cfg["courses"].items():
        p = c["env_prefix"]
        courses[slug] = Course(
            slug, c["full_name"], c["drive_folder"],
            os.environ.get(f"{p}_VIMEO_URL", ""), os.environ.get(f"{p}_VIMEO_PASSWORD", ""),
        )
    return Settings(courses, cfg["frames"], cfg["transcript"], cfg["avisos_keywords"],
                    Path(os.environ.get("DRIVE_ROOT", "")))


def course(settings: Settings, slug: str) -> Course:
    if slug not in settings.courses:
        raise KeyError(f"unknown course '{slug}' (known: {', '.join(settings.courses)})")
    c = settings.courses[slug]
    if not c.showcase_url or not c.password:
        raise RuntimeError(f"missing {slug.upper()}_VIMEO_URL / {slug.upper()}_VIMEO_PASSWORD in .env")
    return c


def class_dirs(slug: str, class_id: str) -> dict[str, Path]:
    return {
        "raw": RAW / slug / class_id,
        "work": WORK / slug / class_id,
        "state": STATE / slug / f"{class_id}.json",
        "note": VAULT / slug / "clases" / f"{class_id}.md",
        "img": VAULT / slug / "clases" / "img" / class_id,
        "vault_course": VAULT / slug,
    }


def glossary_path(slug: str) -> Path:
    return CONFIG / f"glossary-{slug}.txt"
```
`pipeline/__init__.py` y `tests/__init__.py`: vacíos.
Run: `uv run pytest tests/test_config.py -q` · Expected: 3 passed.

- [ ] **Step 4: tests de state (fallan) + state.py**

```python
# tests/test_state.py
from pipeline import state

def test_mark_and_is_done(tmp_path):
    p = tmp_path / "s" / "c.json"
    assert not state.is_done(p, "fetch")
    st = state.mark(p, "fetch", "ok", vtt="x.vtt")
    assert st["stages"]["fetch"]["vtt"] == "x.vtt" and state.is_done(p, "fetch")
    state.mark(p, "fetch", "blocked", error="sin VTT")
    assert not state.is_done(p, "fetch")

def test_set_meta_keeps_stages(tmp_path):
    p = tmp_path / "c.json"
    state.mark(p, "fetch", "ok")
    st = state.set_meta(p, course="arqui", class_id="2026-10-07-clase-15")
    assert st["course"] == "arqui" and state.is_done(p, "fetch")

def test_unknown_stage_rejected(tmp_path):
    import pytest
    with pytest.raises(ValueError):
        state.mark(tmp_path / "c.json", "nope", "ok")

def test_next_pending(tmp_path):
    p = tmp_path / "c.json"
    state.mark(p, "fetch", "ok")
    assert state.next_pending(p) == "transcript"
```

```python
# pipeline/state.py
from __future__ import annotations

import json
from datetime import datetime, timezone
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
    st["stages"][stage] = {"status": status, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"), **extra}
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
```
Run: `uv run pytest -q` · Expected: 7 passed. `uv run ruff check pipeline tests` · Expected: `All checks passed!`

- [ ] **Step 5: herramientas del sistema**
Run: `ffmpeg -version | head -1 && tesseract --list-langs` · Expected: versión de ffmpeg; lista con `spa` y `eng`. Si falta `spa`: `brew install tesseract-lang`.

- [ ] **Step 6: Commit**
```bash
git add pyproject.toml .python-version uv.lock pipeline/__init__.py pipeline/config.py pipeline/state.py tests/__init__.py tests/conftest.py tests/test_config.py tests/test_state.py
git commit -m "feat: project scaffolding with config loading and per-class state"
```

---

## Ola 1 (4 agentes en paralelo)

### Task 2: Listado del showcase y naming de clases

**Files:** Create `pipeline/vimeo.py`, `pipeline/naming.py`, `tests/test_vimeo.py`, `tests/test_naming.py`.
**DoD:** tests verdes con sesión HTTP falsa; `uv run python -c "from pipeline.vimeo import *"` importa; validación manual contra arqui devuelve 15 videos.
**Deliverable:** `VimeoShowcase.list_videos()` → `list[ShowcaseVideo]` ordenada por `created_time`; `assign_ids()`.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_vimeo.py
import json
from pipeline.vimeo import VimeoShowcase, ShowcaseVideo

class FakeResp:
    def __init__(self, status, body): self.status_code, self._b = status, body
    def json(self): return self._b
    def raise_for_status(self):
        if self.status_code >= 400: raise RuntimeError(self.status_code)

class FakeSession:
    def __init__(self, pages, auth_status=200):
        self.pages, self.auth_status, self.calls = pages, auth_status, []
    def get(self, url, params=None, headers=None):
        self.calls.append(("GET", url, params, headers))
        if url.endswith("/_next/viewer"): return FakeResp(200, {"jwt": "J", "xsrft": "X"})
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
    post = [c for c in s.calls if c[0] == "POST"][0]
    assert post[1] == "https://vimeo.com/showcase/9/auth" and post[2] == {"password": "pw", "token": "X"}
    listing = [c for c in s.calls if "/albums/9/videos" in c[1]]
    assert len(listing) == 2 and listing[0][3]["Authorization"] == "jwt J" and listing[0][2]["_hashed_pass"] == "HP"

def test_wrong_password():
    import pytest
    with pytest.raises(PermissionError):
        VimeoShowcase("9", "bad", session=FakeSession([[]], auth_status=401)).list_videos()

# tests/test_naming.py
from datetime import date
from pipeline.naming import class_date, class_id, assign_ids
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
```
Run: `uv run pytest tests/test_vimeo.py tests/test_naming.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/vimeo.py
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
```
```python
# pipeline/naming.py
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
```
Run: `uv run pytest tests/test_vimeo.py tests/test_naming.py -q` · Expected: 5 passed.

- [ ] **Step 3: validación real (no imprimir passwords)**
Run: `set -a; source .env; set +a; uv run python -c "from pipeline.vimeo import VimeoShowcase; import os; vs=VimeoShowcase('12367712', os.environ['ARQUI_VIMEO_PASSWORD']).list_videos(); print(len(vs), vs[0].title)"` · Expected: `15 FI-3851-Arquitectura de software-77930-ID_N7A0826_AR | <fecha>`.

- [ ] **Step 4: Commit**
```bash
git add pipeline/vimeo.py pipeline/naming.py tests/test_vimeo.py tests/test_naming.py
git commit -m "feat: list password-protected Vimeo showcases and derive class ids"
```

### Task 3: VTT → transcript.md

**Files:** Create `pipeline/vtt.py`, `tests/test_vtt.py`, `tests/fixtures/sample.vtt`.
**DoD:** tests verdes (parse con cues repetidos, párrafos de 30 s, glosario, hms); salida cumple contrato 0.4.

- [ ] **Step 1: fixture + tests (fallan)**
```
WEBVTT

00:00:00.000 --> 00:00:03.000
Buenas, arrancamos la clase.

00:00:03.000 --> 00:00:06.000
Buenas, arrancamos la clase.

00:00:06.500 --> 00:00:20.000
Hoy vemos arquitectura en capas
y el patron MVC.

00:00:40.000 --> 00:00:45.000
El parcial es el quince de octubre.
```
```python
# tests/test_vtt.py
from pathlib import Path
from pipeline import vtt

FIX = Path(__file__).parent / "fixtures" / "sample.vtt"

def test_parse_merges_repeated_cues_and_joins_lines():
    cues = vtt.parse(FIX)
    assert [c.text for c in cues] == ["Buenas, arrancamos la clase.", "Hoy vemos arquitectura en capas y el patron MVC.",
                                      "El parcial es el quince de octubre."]
    assert cues[0].start == 0.0 and cues[0].end == 6.0

def test_hms():
    assert vtt.hms(0) == "00:00:00" and vtt.hms(3661.9) == "01:01:01"

def test_paragraphs_every_30s():
    paras = vtt.paragraphs(vtt.parse(FIX), every=30)
    assert [p[0] for p in paras] == [0.0, 40.0]
    assert paras[0][1].startswith("Buenas") and "MVC" in paras[0][1]

def test_glossary_applied(tmp_path):
    g = tmp_path / "g.txt"; g.write_text("patron MVC => patrón MVC  # typo frecuente\n")
    md = vtt.to_markdown(vtt.parse(FIX), "arqui · c1", every=30, glossary=vtt.load_glossary(g))
    assert "[00:00:00]" in md and "patrón MVC" in md and md.startswith("# Transcript · arqui · c1")

def test_convert_writes_file(tmp_path):
    out = tmp_path / "t.md"
    n = vtt.convert(FIX, out, "x")
    assert n == 3 and out.read_text().count("\n[") == 2
```
Run: `uv run pytest tests/test_vtt.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/vtt.py
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import webvtt


@dataclass
class Cue:
    start: float
    end: float
    text: str


def _secs(ts: str) -> float:
    h, m, s = ts.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


def hms(t: float) -> str:
    t = int(t)
    return f"{t // 3600:02d}:{t % 3600 // 60:02d}:{t % 60:02d}"


def parse(path: Path) -> list[Cue]:
    cues: list[Cue] = []
    for c in webvtt.read(str(path)):
        text = re.sub(r"\s+", " ", c.text.replace("\n", " ")).strip()
        if not text:
            continue
        if cues and cues[-1].text == text:  # Vimeo repeats the same caption across adjacent cues
            cues[-1].end = max(cues[-1].end, _secs(c.end))
            continue
        cues.append(Cue(_secs(c.start), _secs(c.end), text))
    return cues


def load_glossary(path: Path | None) -> dict[str, str]:
    """Lines `wrong => right`; `#` starts a comment."""
    if not path or not path.exists():
        return {}
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=>" in line:
            a, b = (x.strip() for x in line.split("=>", 1))
            out[a] = b
    return out


def apply_glossary(text: str, glossary: dict[str, str]) -> str:
    for wrong, right in glossary.items():
        text = re.sub(rf"\b{re.escape(wrong)}\b", right, text, flags=re.IGNORECASE)
    return text


def paragraphs(cues: list[Cue], every: float = 30.0) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    buf: list[str] = []
    start: float | None = None
    for c in cues:
        if start is None:
            start = c.start
        buf.append(c.text)
        if c.start - start >= every:
            out.append((start, " ".join(buf)))
            buf, start = [], None
    if buf and start is not None:
        out.append((start, " ".join(buf)))
    return out


def to_markdown(cues: list[Cue], title: str, every: float = 30.0, glossary: dict[str, str] | None = None) -> str:
    lines = [f"# Transcript · {title}", ""]
    for t, text in paragraphs(cues, every):
        lines.append(f"[{hms(t)}] {apply_glossary(text, glossary or {})}")
    return "\n".join(lines) + "\n"


def convert(vtt_path: Path, out_path: Path, title: str, every: float = 30.0, glossary_path: Path | None = None) -> int:
    cues = parse(vtt_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(to_markdown(cues, title, every, load_glossary(glossary_path)), encoding="utf-8")
    return len(cues)
```
Run: `uv run pytest tests/test_vtt.py -q` · Expected: 5 passed.

- [ ] **Step 3: Commit**
```bash
git add pipeline/vtt.py tests/test_vtt.py tests/fixtures/sample.vtt
git commit -m "feat: convert Vimeo VTT captions into timestamped transcript markdown"
```

### Task 4: Frames clave (muestreo, pHash, OCR, export)

**Files:** Create `pipeline/frames.py`, `pipeline/ocr.py`, `tests/test_frames.py`.
**DoD:** tests unitarios verdes sin ffmpeg (imágenes sintéticas); test de integración con ffmpeg `testsrc` (skip si no hay ffmpeg); `frames.json` cumple 0.5.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_frames.py
import shutil
import subprocess
from pathlib import Path

import pytest
from PIL import Image, ImageDraw

from pipeline import frames


def img(path: Path, color, text: str = ""):
    im = Image.new("RGB", (320, 180), color)
    if text:
        ImageDraw.Draw(im).text((10, 10), text, fill="black")
    im.save(path)
    return path


def test_segments_collapse_identical_consecutive(tmp_path):
    files = [img(tmp_path / f"{i:05d}.jpg", "white", "slide A") for i in range(3)]
    files += [img(tmp_path / f"{i:05d}.jpg", (20, 20, 20), "") for i in range(3, 5)]
    segs = frames.segments(files, every=10, same_dist=6)
    assert [(s.t, s.t_end) for s in segs] == [(0.0, 30.0), (30.0, 50.0)]


def test_global_dups_marked(tmp_path):
    a = img(tmp_path / "a.jpg", "white", "slide A"); b = img(tmp_path / "b.jpg", (20, 20, 20)); a2 = img(tmp_path / "c.jpg", "white", "slide A")
    segs = frames.segments([a, b, a2], every=10, same_dist=6)
    frames.mark_global_dups(segs, same_dist=6)
    assert segs[2].dup_of == 0 and segs[1].dup_of is None


def test_decide_keep_rules():
    s = [frames.Segment(0, 0, 60, "f", "0" * 16, ocr="uno dos tres cuatro cinco"),
         frames.Segment(1, 60, 65, "f", "0" * 16, ocr="texto corto pero muchas palabras aqui"),
         frames.Segment(2, 65, 200, "f", "0" * 16, ocr="hola"),
         frames.Segment(3, 200, 300, "f", "0" * 16, ocr="a b c d e", dup_of=0)]
    frames.decide_keep(s, min_seconds=8)
    assert [x.keep for x in s] == [True, False, False, False]
    assert s[1].reason == "too_short" and s[2].reason == "no_text" and s[3].reason == "dup_of:0"


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_sample_and_export_with_ffmpeg(tmp_path):
    video = tmp_path / "v.mp4"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=25:size=320x180:rate=5",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    files = frames.sample(video, tmp_path / "sample", every=10)
    assert len(files) == 3
    segs = frames.segments(files, every=10, same_dist=6)
    for s in segs:
        s.keep = True
    out = frames.export(video, segs, tmp_path / "img", width=160)
    assert len(out) == len(segs) and all(p.exists() for p in out)
    frames.write_manifest(tmp_path / "frames.json", "c1", 10, segs)
    assert '"class_id": "c1"' in (tmp_path / "frames.json").read_text()
```
Run: `uv run pytest tests/test_frames.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/ocr.py
from __future__ import annotations

from pathlib import Path

import pytesseract
from PIL import Image


def text(path: Path, lang: str = "spa+eng") -> str:
    with Image.open(path) as im:
        return " ".join(pytesseract.image_to_string(im, lang=lang).split())


def ocr_segments(segs, lang: str = "spa+eng") -> None:
    for s in segs:
        s.ocr = text(Path(s.file), lang)
```
```python
# pipeline/frames.py
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from pathlib import Path

import imagehash
from PIL import Image


@dataclass
class Segment:
    idx: int
    t: float
    t_end: float
    file: str
    phash: str
    ocr: str = ""
    keep: bool = False
    reason: str = ""
    dup_of: int | None = None


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True)


def sample(video: Path, out_dir: Path, every: int, width: int = 640) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video),
          "-vf", f"fps=1/{every},scale={width}:-2", "-q:v", "4", str(out_dir / "%05d.jpg")])
    return sorted(out_dir.glob("*.jpg"))


def phash(path: Path) -> imagehash.ImageHash:
    with Image.open(path) as im:
        return imagehash.phash(im)


def segments(files: list[Path], every: int, same_dist: int) -> list[Segment]:
    """Collapse runs of visually identical consecutive frames into one segment each."""
    segs: list[Segment] = []
    prev = None
    for i, f in enumerate(files):
        h = phash(f)
        t = float(i * every)
        if prev is not None and (h - prev) <= same_dist:
            segs[-1].t_end = t + every
            continue
        segs.append(Segment(len(segs), t, t + every, str(f), str(h)))
        prev = h
    return segs


def mark_global_dups(segs: list[Segment], same_dist: int) -> None:
    """The professor goes back to an earlier slide: keep one image, point the rest at it."""
    kept: list[tuple[int, imagehash.ImageHash]] = []
    for s in segs:
        h = imagehash.hex_to_hash(s.phash)
        for idx, kh in kept:
            if (h - kh) <= same_dist:
                s.dup_of = idx
                break
        else:
            kept.append((s.idx, h))


def decide_keep(segs: list[Segment], min_seconds: float, min_words: int = 4) -> None:
    for s in segs:
        words = len(s.ocr.split())
        if s.dup_of is not None:
            s.keep, s.reason = False, f"dup_of:{s.dup_of}"
        elif s.t_end - s.t < min_seconds:
            s.keep, s.reason = False, "too_short"
        elif words < min_words:
            s.keep, s.reason = False, "no_text"
        else:
            s.keep, s.reason = True, f"text:{words}w"


def export(video: Path, segs: list[Segment], out_dir: Path, width: int) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for s in segs:
        if not s.keep:
            continue
        dest = out_dir / f"{s.idx:04d}.jpg"
        _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{(s.t + s.t_end) / 2:.2f}", "-i", str(video),
              "-frames:v", "1", "-vf", f"scale={width}:-2", "-q:v", "3", str(dest)])
        s.file = str(dest)
        out.append(dest)
    return out


def write_manifest(path: Path, class_id: str, every: int, segs: list[Segment]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"class_id": class_id, "sample_every": every, "frames": [asdict(s) for s in segs]},
                               ensure_ascii=False, indent=1), encoding="utf-8")


def process(video: Path, work_dir: Path, img_dir: Path, class_id: str, cfg: dict, ocr_fn=None) -> list[Segment]:
    """Full pass: sample -> segments -> OCR -> dedupe -> keep -> export -> frames.json."""
    from .ocr import ocr_segments

    every, dist = int(cfg["sample_every_seconds"]), int(cfg["phash_distance_same"])
    files = sample(video, work_dir / "sample", every)
    segs = segments(files, every, dist)
    (ocr_fn or ocr_segments)(segs)
    mark_global_dups(segs, dist)
    decide_keep(segs, float(cfg["min_slide_seconds"]))
    export(video, segs, img_dir, int(cfg["export_width"]))
    write_manifest(work_dir / "frames.json", class_id, every, segs)
    return segs
```
Run: `uv run pytest tests/test_frames.py -q` · Expected: 4 passed (o 3 passed + 1 skipped sin ffmpeg).

- [ ] **Step 3: Commit**
```bash
git add pipeline/frames.py pipeline/ocr.py tests/test_frames.py
git commit -m "feat: extract, dedupe and OCR key frames from class videos"
```

### Task 5: Validador de notas

**Files:** Create `pipeline/note_validate.py`, `tests/test_note_validate.py`.
**DoD:** detecta frontmatter faltante, sección faltante/desordenada, imagen rota, wikilink roto, ausencia de timestamps; nota válida → `[]`.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_note_validate.py
from pathlib import Path
from pipeline import note_validate as nv

GOOD = """---
curso: arqui
fecha: 2026-10-07
numero: 15
titulo: Capas
duracion: 7010
vimeo_url: https://vimeo.com/showcase/1/video/2
video_path: raw/arqui/x/video.mp4
estado: borrador
tags: [clase]
---
# arqui · Clase 15
## Resumen ejecutivo
Vimos capas [00:01:00].
## ⚠️ Avisos del profesor
—
## Índice de temas
- [[arquitectura-en-capas]]
## Desarrollo por tema
![](img/c/0001.jpg)
## Conceptos y definiciones
—
## Ejemplos, demos y código
—
## Preguntas de alumnos y respuestas
—
## Dudas / a verificar
—
## Citas textuales relevantes
—
## Material referenciado
—
"""

def make(tmp_path: Path, text: str) -> tuple[Path, Path]:
    vault = tmp_path / "vault"; (vault / "arqui" / "clases" / "img" / "c").mkdir(parents=True)
    (vault / "arqui" / "temas").mkdir(); (vault / "arqui" / "temas" / "arquitectura-en-capas.md").write_text("# t")
    (vault / "arqui" / "clases" / "img" / "c" / "0001.jpg").write_bytes(b"x")
    note = vault / "arqui" / "clases" / "c.md"; note.write_text(text, encoding="utf-8")
    return note, vault

def test_valid_note_has_no_errors(tmp_path):
    note, vault = make(tmp_path, GOOD)
    assert nv.validate(note, vault) == []

def test_detects_problems(tmp_path):
    bad = GOOD.replace("## Índice de temas\n", "").replace("0001.jpg", "0009.jpg").replace("[[arquitectura-en-capas]]", "[[nope]]").replace("[00:01:00]", "")
    bad = bad.replace("estado: borrador\n", "")
    note, vault = make(tmp_path, bad)
    errs = nv.validate(note, vault)
    assert any("Índice de temas" in e for e in errs)
    assert any("0009.jpg" in e for e in errs)
    assert any("[[nope]]" in e for e in errs)
    assert any("timestamps" in e for e in errs)
    assert any("'estado'" in e for e in errs)

def test_section_order(tmp_path):
    swapped = GOOD.replace("## Resumen ejecutivo\nVimos capas [00:01:00].\n## ⚠️ Avisos del profesor\n—\n",
                           "## ⚠️ Avisos del profesor\n—\n## Resumen ejecutivo\nVimos capas [00:01:00].\n")
    note, vault = make(tmp_path, swapped)
    assert "secciones fuera de orden" in nv.validate(note, vault)
```
Run: `uv run pytest tests/test_note_validate.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/note_validate.py
from __future__ import annotations

import re
from pathlib import Path

REQUIRED_FM = ["curso", "fecha", "numero", "titulo", "duracion", "vimeo_url", "video_path", "estado", "tags"]
REQUIRED_H2 = ["Resumen ejecutivo", "⚠️ Avisos del profesor", "Índice de temas", "Desarrollo por tema",
               "Conceptos y definiciones", "Ejemplos, demos y código", "Preguntas de alumnos y respuestas",
               "Dudas / a verificar", "Citas textuales relevantes", "Material referenciado"]
IMG = re.compile(r"!\[[^\]]*\]\(([^)]+)\)")
WIKI = re.compile(r"\[\[([^\]|#]+)(?:[#|][^\]]*)?\]\]")
TS = re.compile(r"\[\d\d:\d\d:\d\d\]")


def frontmatter(text: str) -> dict[str, str]:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def validate(note: Path, vault: Path) -> list[str]:
    text = note.read_text(encoding="utf-8")
    errs: list[str] = []
    fm = frontmatter(text)
    if not fm:
        errs.append("frontmatter ausente")
    for k in REQUIRED_FM:
        if not fm.get(k):
            errs.append(f"frontmatter sin '{k}'")
    heads = [h.strip() for h in re.findall(r"^## (.+)$", text, re.M)]
    for h in REQUIRED_H2:
        if h not in heads:
            errs.append(f"falta sección '## {h}'")
    order = [heads.index(h) for h in REQUIRED_H2 if h in heads]
    if order != sorted(order):
        errs.append("secciones fuera de orden")
    for rel in IMG.findall(text):
        if not rel.startswith("http") and not (note.parent / rel).exists():
            errs.append(f"imagen inexistente: {rel}")
    names = {p.stem for p in vault.rglob("*.md")}
    for link in WIKI.findall(text):
        if link.strip() not in names:
            errs.append(f"wikilink roto: [[{link}]]")
    if not TS.search(text):
        errs.append("sin timestamps [hh:mm:ss]")
    return errs
```
Run: `uv run pytest tests/test_note_validate.py -q` · Expected: 3 passed.

- [ ] **Step 3: Commit**
```bash
git add pipeline/note_validate.py tests/test_note_validate.py
git commit -m "feat: structural validator for class notes"
```

---

## Ola 2 (4 agentes en paralelo; requiere Ola 1 en master)

### Task 6: Fetch (yt-dlp sobre la embed URL firmada)

**Files:** Create `pipeline/fetch.py`, `tests/test_fetch.py`.
**DoD:** tests con `download` y `list_videos` falsos verdes; `fetch_course(..., subs_only=True)` real sobre arqui deja 15 `.vtt` en `raw/arqui/*/` y 15 estados `fetch: ok`.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_fetch.py
from pipeline import fetch, state, config
from pipeline.vimeo import ShowcaseVideo

def _course():
    return config.Course("arqui", "Arq", "ArqSoft", "https://vimeo.com/showcase/9", "pw")

def test_fetch_course_marks_ok_and_blocked(monkeypatch, tmp_path):
    monkeypatch.setattr(config, "RAW", tmp_path / "raw"); monkeypatch.setattr(config, "STATE", tmp_path / "state")
    monkeypatch.setattr(config, "WORK", tmp_path / "work"); monkeypatch.setattr(config, "VAULT", tmp_path / "vault")
    vids = [ShowcaseVideo("1", "a | 30-09-2026", 10, "2026-10-01T00:00:00+00:00", "u1"),
            ShowcaseVideo("2", "b | 07-10-2026", 10, "2026-10-08T00:00:00+00:00", "u2")]
    monkeypatch.setattr(fetch.VimeoShowcase, "list_videos", lambda self: vids)
    def fake_download(video, dest, subs_only):
        dest.mkdir(parents=True, exist_ok=True)
        if video.video_id == "1":
            (dest / "video.es-x-autogen.vtt").write_text("WEBVTT\n")
            return {"vtt": str(dest / "video.es-x-autogen.vtt"), "video": None, "subs_langs": ["es-x-autogen"]}
        return {"vtt": None, "video": None, "subs_langs": []}
    monkeypatch.setattr(fetch, "download", fake_download)
    res = fetch.fetch_course(_course(), subs_only=True)
    assert [r["class_id"] for r in res] == ["2026-09-30-clase-01", "2026-10-07-clase-02"]
    s1 = state.load(config.class_dirs("arqui", "2026-09-30-clase-01")["state"])
    s2 = state.load(config.class_dirs("arqui", "2026-10-07-clase-02")["state"])
    assert s1["stages"]["fetch"]["status"] == "ok" and s1["title"] == "a | 30-09-2026"
    assert s2["stages"]["fetch"]["status"] == "blocked" and "sin VTT" in s2["stages"]["fetch"]["error"]
    # second run with subs_only skips the ok one
    res2 = fetch.fetch_course(_course(), subs_only=True)
    assert res2[0].get("skipped") is True

def test_ydl_opts_contract(tmp_path):
    o = fetch.ydl_opts(tmp_path, subs_only=True, max_height=720)
    assert o["skip_download"] is True and o["subtitleslangs"] == ["all"] and o["http_headers"]["Referer"] == "https://vimeo.com/"
    assert o["format"].startswith("bv*[height<=720]")
```
Run: `uv run pytest tests/test_fetch.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/fetch.py
from __future__ import annotations

from pathlib import Path

import yt_dlp

from . import config, state
from .config import Course
from .naming import assign_ids
from .vimeo import ShowcaseVideo, VimeoShowcase


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
        "retries": 5,
    }


def download(video: ShowcaseVideo, dest: Path, subs_only: bool) -> dict:
    """Downloads into dest. Returns {vtt, video, subs_langs}; vtt is None when Vimeo exposes no track."""
    dest.mkdir(parents=True, exist_ok=True)
    with yt_dlp.YoutubeDL(ydl_opts(dest, subs_only)) as ydl:
        info = ydl.extract_info(video.embed_url, download=True)
    vtts = sorted(dest.glob("video.*.vtt"))
    mp4 = dest / "video.mp4"
    return {
        "vtt": str(vtts[0]) if vtts else None,
        "video": str(mp4) if mp4.exists() else None,
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
        except Exception as e:  # yt_dlp.utils.DownloadError and network errors: class stays blocked, loop continues
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
```
Run: `uv run pytest tests/test_fetch.py -q` · Expected: 2 passed.

- [ ] **Step 3: validación real (solo subtítulos, rápido)**
Run: `set -a; source .env; set +a; uv run python -c "from pipeline import config, fetch; s=config.load_settings(); print(fetch.fetch_course(config.course(s,'arqui'), subs_only=True))" | head -c 1500 && ls raw/arqui | head && ls raw/arqui/*/ | grep -c vtt`
Expected: 15 directorios `2026-..-clase-NN`, 15 `.vtt`. Si alguno queda `blocked`, anotarlo en `_meta/PROGRESS.md` (no inventar transcript).

- [ ] **Step 4: Commit**
```bash
git add pipeline/fetch.py tests/test_fetch.py
git commit -m "feat: download showcase videos, captions and metadata with yt-dlp"
```

### Task 7: Avisos (prefiltro), armado del prompt y runner `claude -p`

**Files:** Create `pipeline/avisos.py`, `pipeline/prompt_builder.py`, `pipeline/runner.py`, `tests/test_avisos.py`, `tests/test_prompt_builder.py`.
**DoD:** tests verdes; `analysis-prompt.md` contiene rol + metadatos + rutas de salida + plantilla + tabla de frames + transcript; `avisos-excerpts.md` contiene fragmentos ±60 s con keywords.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_avisos.py
from pipeline import avisos

T = """# Transcript · x

[00:00:00] arrancamos con capas
[00:00:30] el parcial es el quince de octubre
[00:01:00] sigamos con MVC
[00:03:00] la entrega del obligatorio es el viernes
"""

def test_excerpts_with_context(tmp_path):
    p = tmp_path / "t.md"; p.write_text(T, encoding="utf-8")
    paras = avisos.read_transcript(p)
    assert paras[1] == (30, "el parcial es el quince de octubre")
    hits = avisos.excerpts(paras, ["parcial", "entrega", "obligatorio"], context=60)
    assert [h["t"] for h in hits] == [30, 180]
    assert hits[0]["keywords"] == ["parcial"] and "arrancamos" in hits[0]["text"] and "MVC" in hits[0]["text"]
    assert hits[1]["keywords"] == ["entrega", "obligatorio"]
    md = avisos.to_markdown(hits)
    assert md.startswith("# Fragmentos") and "## [00:00:30] parcial" in md

# tests/test_prompt_builder.py
import json
from pipeline import prompt_builder as pb

def test_frames_table_only_kept(tmp_path):
    m = tmp_path / "frames.json"
    m.write_text(json.dumps({"class_id": "c", "sample_every": 10, "frames": [
        {"idx": 1, "t": 10, "t_end": 70, "file": "/x/img/0001.jpg", "phash": "", "ocr": "Capas | logica", "keep": True, "reason": "", "dup_of": None},
        {"idx": 2, "t": 70, "t_end": 80, "file": "/x/s.jpg", "phash": "", "ocr": "", "keep": False, "reason": "", "dup_of": None}]}))
    table = pb.frames_table(m)
    assert "0001.jpg" in table and "s.jpg" not in table and "00:00:10–00:01:10" in table and "Capas / logica" in table

def test_build_prompt_has_all_blocks(tmp_path, repo_root):
    m = tmp_path / "frames.json"; m.write_text(json.dumps({"class_id": "c", "sample_every": 10, "frames": []}))
    t = tmp_path / "transcript.md"; t.write_text("# Transcript · c\n\n[00:00:00] hola\n")
    meta = {"curso": "arqui", "class_id": "c"}
    out = pb.build_analysis_prompt(meta, t, m, tmp_path / "c.md", tmp_path / "temas.json", "img/c")
    for needle in ("## Metadatos", '"curso": "arqui"', "## Salidas obligatorias", "## Plantilla de la nota", "## Frames disponibles",
                   "## Transcript", "[00:00:00] hola", "![](img/c/<archivo>)", "## Resumen ejecutivo"):
        assert needle in out
    assert out.startswith((repo_root / "prompts" / "analista-clase.md").read_text(encoding="utf-8")[:40])
```
Run: `uv run pytest tests/test_avisos.py tests/test_prompt_builder.py -q` · Expected: FAIL (ImportError). Nota: `prompts/analista-clase.md` lo crea Task 11; para que este test corra en Ola 2, crear ahora un placeholder mínimo con la primera línea `# Rol: analista de clase` (Task 11 lo reemplaza por el texto completo, misma primera línea).

- [ ] **Step 2: implementación**
```python
# pipeline/avisos.py
from __future__ import annotations

import re
from pathlib import Path

from .vtt import hms

LINE = re.compile(r"^\[(\d\d):(\d\d):(\d\d)\] (.*)$")


def read_transcript(path: Path) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = LINE.match(line)
        if m:
            h, mi, s, text = m.groups()
            out.append((int(h) * 3600 + int(mi) * 60 + int(s), text))
    return out


def excerpts(paras: list[tuple[int, str]], keywords: list[str], context: int = 60) -> list[dict]:
    pat = re.compile("|".join(re.escape(k) for k in keywords), re.IGNORECASE)
    hits: list[dict] = []
    for t, text in paras:
        found = sorted({m.group(0).lower() for m in pat.finditer(text)})
        if not found:
            continue
        ctx = [p for p in paras if t - context <= p[0] <= t + context]
        hits.append({"t": t, "keywords": found, "text": " ".join(x[1] for x in ctx)})
    return hits


def to_markdown(hits: list[dict]) -> str:
    lines = ["# Fragmentos con keywords de avisos", ""]
    for h in hits:
        lines.append(f"## [{hms(h['t'])}] {', '.join(h['keywords'])}\n{h['text']}\n")
    return "\n".join(lines)
```
```python
# pipeline/prompt_builder.py
from __future__ import annotations

import json
from pathlib import Path

from .config import PROMPTS, TEMPLATES
from .vtt import hms


def frames_table(manifest: Path, max_ocr: int = 200) -> str:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    rows = ["| t | archivo | OCR (recorte) |", "|---|---|---|"]
    for f in data["frames"]:
        if not f["keep"]:
            continue
        rows.append(f"| {hms(f['t'])}–{hms(f['t_end'])} | {Path(f['file']).name} | {f['ocr'][:max_ocr].replace('|', '/')} |")
    return "\n".join(rows)


def build_analysis_prompt(meta: dict, transcript: Path, manifest: Path, note_path: Path, temas_path: Path, img_rel: str) -> str:
    role = (PROMPTS / "analista-clase.md").read_text(encoding="utf-8")
    template = (TEMPLATES / "clase.md").read_text(encoding="utf-8")
    return "\n\n".join([
        role,
        "## Metadatos\n```json\n" + json.dumps(meta, ensure_ascii=False, indent=1) + "\n```",
        "## Salidas obligatorias\n"
        f"- Nota: `{note_path}`\n- Temas candidatos: `{temas_path}`\n"
        f"- Las imágenes se referencian como `![]({img_rel}/<archivo>)` usando solo archivos de la tabla de frames.",
        "## Plantilla de la nota (respetar frontmatter, secciones y orden)\n```markdown\n" + template + "\n```",
        "## Frames disponibles (podés abrir el archivo con Read para verlo)\n" + frames_table(manifest),
        "## Transcript\n" + transcript.read_text(encoding="utf-8"),
    ])


def build_avisos_prompt(meta: dict, excerpts_md: Path, note_path: Path, review_path: Path) -> str:
    role = (PROMPTS / "verificador-avisos.md").read_text(encoding="utf-8")
    return "\n\n".join([
        role,
        "## Metadatos\n```json\n" + json.dumps(meta, ensure_ascii=False, indent=1) + "\n```",
        f"## Entradas\n- Nota a revisar: `{note_path}` (leer solo la sección ⚠️ Avisos del profesor)\n- Fragmentos: abajo\n"
        f"## Salida\n- Escribir el informe en `{review_path}`",
        excerpts_md.read_text(encoding="utf-8"),
    ])
```
```python
# pipeline/runner.py
from __future__ import annotations

import json
import subprocess
from pathlib import Path


def run_claude(prompt_path: Path, model: str, budget_usd: float, max_turns: int = 20,
               allowed_tools: tuple[str, ...] = ("Read", "Write"), timeout_s: int = 1800) -> dict:
    """Headless Claude Code run with a hard budget. Returns {cost_usd, turns, result}. Raises on non-zero exit."""
    cmd = ["claude", "-p", "--model", model, "--max-turns", str(max_turns), "--max-budget-usd", str(budget_usd),
           "--allowedTools", ",".join(allowed_tools), "--output-format", "json"]
    r = subprocess.run(cmd, input=prompt_path.read_text(encoding="utf-8"), capture_output=True, text=True, timeout=timeout_s)
    if r.returncode != 0:
        raise RuntimeError(f"claude -p failed ({r.returncode}): {r.stderr[-800:]}")
    out = json.loads(r.stdout)
    return {"cost_usd": out.get("total_cost_usd"), "turns": out.get("num_turns"), "result": (out.get("result") or "")[:500]}
```
Run: `uv run pytest tests/test_avisos.py tests/test_prompt_builder.py -q` · Expected: 3 passed. Verificar flags: `claude -p --help | grep -E "max-budget-usd|allowedTools|output-format"` · Expected: las tres aparecen (si el nombre difiere, ajustar `runner.py` y anotarlo en DECISIONES).

- [ ] **Step 3: Commit**
```bash
git add pipeline/avisos.py pipeline/prompt_builder.py pipeline/runner.py tests/test_avisos.py tests/test_prompt_builder.py prompts/analista-clase.md
git commit -m "feat: avisos prefilter, analysis prompt builder and headless claude runner"
```

### Task 8: Integración al vault (temas, MOC, avisos, calendario) y canvas

**Files:** Create `pipeline/integrate.py`, `pipeline/canvas.py`, `tests/test_integrate.py`, `tests/test_canvas.py`. Modify `templates/tema.md` (sin cambios de secciones).
**DoD:** upsert de temas idempotente; MOC regenerado solo entre marcadores; `avisos-<curso>.md` compilado; `calendario.md` con líneas fechadas; `.canvas` JSON válido con nodos `file` para wikilinks resueltos.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_integrate.py
import json
from pipeline import integrate as it

CAND = {"titulo": "Arquitectura en capas", "resumen": "Separar presentación, lógica y datos.\nSegunda línea.",
        "timestamps": ["00:12:30"], "relacionados": ["Acoplamiento y cohesión"]}

def test_slugify():
    assert it.slugify("Acoplamiento y cohesión") == "acoplamiento-y-cohesion"

def test_upsert_tema_create_update_unchanged(tmp_path):
    vc = tmp_path / "arqui"
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-07-clase-15") == "created"
    t = (vc / "temas" / "arquitectura-en-capas.md").read_text(encoding="utf-8")
    assert t.startswith("---\ncurso: arqui\ntema: Arquitectura en capas") and "- [[acoplamiento-y-cohesion]]" in t
    assert "- [[2026-10-07-clase-15]] · 00:12:30 — Separar presentación" in t
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-14-clase-16") == "updated"
    assert it.upsert_tema(vc, "arqui", CAND, "2026-10-14-clase-16") == "unchanged"
    assert (vc / "temas" / "arquitectura-en-capas.md").read_text().count("[[2026-10-14-clase-16]]") == 1

def test_regen_moc_preserves_manual_part(tmp_path):
    vc = tmp_path / "arqui"; (vc / "temas").mkdir(parents=True); (vc / "clases").mkdir()
    (vc / "temas" / "capas.md").write_text("x"); (vc / "clases" / "2026-10-07-clase-15.md").write_text("x")
    moc = it.regen_moc(vc, "arqui", "Arquitectura de Software")
    text = moc.read_text(encoding="utf-8")
    assert "- [[capas]]" in text and "- [[2026-10-07-clase-15]]" in text and text.count(it.MARK_START) == 1
    moc.write_text(text.replace("## Mapa", "## Mapa\n- Manual [[capas]]"), encoding="utf-8")
    (vc / "temas" / "mvc.md").write_text("x")
    text2 = it.regen_moc(vc, "arqui", "Arquitectura de Software").read_text(encoding="utf-8")
    assert "- Manual [[capas]]" in text2 and "- [[mvc]]" in text2 and text2.count(it.MARK_START) == 1

def test_avisos_and_calendario(tmp_path):
    vault = tmp_path; vc = vault / "arqui"; (vc / "clases").mkdir(parents=True)
    (vc / "clases" / "2026-10-07-clase-15.md").write_text(
        "## Resumen ejecutivo\nx\n## ⚠️ Avisos del profesor\n- Parcial el 15/10 [00:00:30]\n- Traer laptop\n## Índice de temas\n—\n", encoding="utf-8")
    p = it.regen_avisos(vc, "arqui")
    assert "## [[2026-10-07-clase-15]]" in p.read_text() and "Traer laptop" in p.read_text()
    cal = it.regen_calendario(vault, ["arqui"]).read_text(encoding="utf-8")
    assert "| arqui | [[2026-10-07-clase-15]] | - Parcial el 15/10 [00:00:30] |" in cal and "laptop" not in cal

# tests/test_canvas.py
import json
from pipeline import canvas

MOC = "# X\n\n## Mapa\n- Fundamentos\n  - [[capas]]\n  - [[mvc]]\n- Calidad\n  - [[acoplamiento]]\n\n<!-- generated:start -->\n- [[ignorado]]\n<!-- generated:end -->\n"

def test_outline_ignores_generated():
    assert canvas.outline(MOC) == [(0, "Fundamentos"), (1, "[[capas]]"), (1, "[[mvc]]"), (0, "Calidad"), (1, "[[acoplamiento]]")]

def test_to_canvas_tree():
    resolve = lambda name: f"arqui/temas/{name}.md" if name != "mvc" else None
    c = canvas.to_canvas("Arq", canvas.outline(MOC), resolve)
    assert c["nodes"][0]["id"] == "root" and len(c["nodes"]) == 6 and len(c["edges"]) == 5
    capas = next(n for n in c["nodes"] if n.get("file") == "arqui/temas/capas.md")
    mvc = next(n for n in c["nodes"] if n.get("text") == "[[mvc]]")
    assert capas["type"] == "file" and mvc["type"] == "text"
    e = next(e for e in c["edges"] if e["toNode"] == capas["id"])
    assert e["fromNode"] == next(n for n in c["nodes"] if n.get("text") == "Fundamentos")["id"]
    json.dumps(c)
```
Run: `uv run pytest tests/test_integrate.py tests/test_canvas.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/integrate.py
from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from .config import TEMPLATES

MARK_START, MARK_END = "<!-- generated:start -->", "<!-- generated:end -->"
DATE = re.compile(
    r"\b\d{1,2}[/-]\d{1,2}(?:[/-]\d{2,4})?\b|\b\d{1,2} de (?:enero|febrero|marzo|abril|mayo|junio|julio|agosto|"
    r"septiembre|setiembre|octubre|noviembre|diciembre)\b", re.I)


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def upsert_tema(vault_course: Path, course: str, cand: dict, class_id: str) -> str:
    """cand: {slug?, titulo, resumen, timestamps:[hh:mm:ss], relacionados:[titulo]} -> created|updated|unchanged."""
    slug = cand.get("slug") or slugify(cand["titulo"])
    path = vault_course / "temas" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    first = cand["resumen"].strip().splitlines()[0][:160]
    seen = f"- [[{class_id}]] · {', '.join(cand.get('timestamps') or [])} — {first}"
    if not path.exists():
        tpl = (TEMPLATES / "tema.md").read_text(encoding="utf-8")
        body = tpl.replace("{{tema}}", cand["titulo"]).replace("curso: \n", f"curso: {course}\n", 1)
        body = body.replace("tema: \n", f"tema: {cand['titulo']}\n", 1)
        body = body.replace("## Ideas clave\n", "## Ideas clave\n" + cand["resumen"].strip() + "\n")
        rel = "".join(f"- [[{slugify(r)}]]\n" for r in cand.get("relacionados") or [])
        body = body.replace("## Relacionado\n", "## Relacionado\n" + rel).replace("## Visto en\n", "## Visto en\n" + seen + "\n")
        path.write_text(body, encoding="utf-8")
        return "created"
    text = path.read_text(encoding="utf-8")
    if f"[[{class_id}]]" in text:
        return "unchanged"
    if "## Visto en" not in text:
        text = text.rstrip("\n") + "\n\n## Visto en\n"
    path.write_text(text.rstrip("\n") + "\n" + seen + "\n", encoding="utf-8")
    return "updated"


def regen_moc(vault_course: Path, course: str, full_name: str) -> Path:
    moc = vault_course / f"MOC-{course}.md"
    temas = sorted(p.stem for p in (vault_course / "temas").glob("*.md"))
    clases = sorted(p.stem for p in (vault_course / "clases").glob("*.md"))
    gen = "\n".join([MARK_START, "## Clases", *[f"- [[{c}]]" for c in clases], "", "## Temas (A–Z)",
                     *[f"- [[{t}]]" for t in temas], MARK_END])
    if moc.exists():
        text = moc.read_text(encoding="utf-8")
        if MARK_START in text and MARK_END in text:
            pre, rest = text.split(MARK_START, 1)
            _, post = rest.split(MARK_END, 1)
            text = pre + gen + post
        else:
            text = text.rstrip() + "\n\n" + gen + "\n"
    else:
        text = (f"# {full_name} — mapa de contenido\n\n## Mapa\n"
                "(outline jerárquico editable a mano; el agente integrador lo organiza)\n\n" + gen + "\n")
    moc.write_text(text, encoding="utf-8")
    return moc


def section(text: str, title: str) -> str:
    m = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    return m.group(1).strip() if m else ""


def regen_avisos(vault_course: Path, course: str) -> Path:
    out = [f"# Avisos del profesor — {course}", ""]
    for note in sorted((vault_course / "clases").glob("*.md")):
        body = section(note.read_text(encoding="utf-8"), "⚠️ Avisos del profesor")
        if body and body != "—":
            out += [f"## [[{note.stem}]]", body, ""]
    p = vault_course / f"avisos-{course}.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p


def regen_calendario(vault: Path, courses: list[str]) -> Path:
    rows = ["# Calendario (líneas de avisos que mencionan una fecha)", "", "| curso | clase | línea |", "|---|---|---|"]
    for c in courses:
        p = vault / c / f"avisos-{c}.md"
        if not p.exists():
            continue
        cur = ""
        for line in p.read_text(encoding="utf-8").splitlines():
            if line.startswith("## [["):
                cur = line[3:].strip()
                continue
            if DATE.search(line):
                rows.append(f"| {c} | {cur} | {line.strip().replace('|', '/')} |")
    out = vault / "calendario.md"
    out.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return out
```
```python
# pipeline/canvas.py
from __future__ import annotations

import re
from collections.abc import Callable

WIKI = re.compile(r"\[\[([^\]|#]+)")


def outline(md: str) -> list[tuple[int, str]]:
    """Nested '- ' list before the generated markers -> [(depth, label)]. Two spaces per level."""
    md = md.split("<!-- generated:start -->")[0]
    out: list[tuple[int, str]] = []
    for line in md.splitlines():
        m = re.match(r"^(\s*)- (.+)$", line)
        if m:
            out.append((len(m.group(1)) // 2, m.group(2).strip()))
    return out


def to_canvas(title: str, items: list[tuple[int, str]], resolve: Callable[[str], str | None]) -> dict:
    """Obsidian .canvas JSON (nodes+edges). Wikilinks that `resolve` maps to a vault path become file nodes."""
    nodes = [{"id": "root", "type": "text", "text": f"# {title}", "x": 0, "y": 0, "width": 320, "height": 80}]
    edges: list[dict] = []
    stack: list[str] = []
    ypos: dict[int, int] = {}
    for i, (depth, label) in enumerate(items):
        link = WIKI.search(label)
        path = resolve(link.group(1).strip()) if link else None
        node: dict = {"id": f"n{i}", "x": 400 * (depth + 1), "y": ypos.get(depth, 0), "width": 300, "height": 70}
        node.update({"type": "file", "file": path} if path else {"type": "text", "text": label})
        ypos[depth] = ypos.get(depth, 0) + 100
        stack = stack[:depth]
        parent = stack[-1] if stack else "root"
        edges.append({"id": f"e{i}", "fromNode": parent, "toNode": node["id"], "fromSide": "right", "toSide": "left"})
        nodes.append(node)
        stack.append(node["id"])
    return {"nodes": nodes, "edges": edges}
```
Run: `uv run pytest tests/test_integrate.py tests/test_canvas.py -q` · Expected: 6 passed.

- [ ] **Step 3: Commit**
```bash
git add pipeline/integrate.py pipeline/canvas.py tests/test_integrate.py tests/test_canvas.py
git commit -m "feat: merge topics into the vault, regenerate MOC/avisos/calendario and build canvas maps"
```

### Task 9: Sync a Drive

**Files:** Create `pipeline/sync.py`, `tests/test_sync.py`.
**DoD:** `move_raw` mueve todo el contenido de `raw/<c>/<id>/` a `_clases-dump/<c>/<id>/`; `mirror_vault` espeja `vault/<c>/` en `<drive_folder>/notas/` con rsync y excluye `.obsidian`.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_sync.py
from pipeline import sync

def test_move_raw(tmp_path):
    raw = tmp_path / "raw" / "arqui" / "c1"; raw.mkdir(parents=True); (raw / "video.mp4").write_bytes(b"v"); (raw / "video.es.vtt").write_text("w")
    dest = sync.move_raw(raw, tmp_path / "dump", "arqui", "c1")
    assert (dest / "video.mp4").exists() and (dest / "video.es.vtt").exists() and not any(raw.iterdir())

def test_mirror_vault(tmp_path):
    vc = tmp_path / "vault" / "arqui"; (vc / "clases").mkdir(parents=True); (vc / ".obsidian").mkdir()
    (vc / "clases" / "c1.md").write_text("n"); (vc / ".obsidian" / "x").write_text("x")
    drive_course = tmp_path / "Drive" / "ArqSoft"
    sync.mirror_vault(vc, drive_course)
    assert (drive_course / "notas" / "clases" / "c1.md").exists() and not (drive_course / "notas" / ".obsidian").exists()
    (vc / "clases" / "c1.md").unlink(); sync.mirror_vault(vc, drive_course)
    assert not (drive_course / "notas" / "clases" / "c1.md").exists()
```
Run: `uv run pytest tests/test_sync.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: implementación**
```python
# pipeline/sync.py
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def move_raw(raw_dir: Path, dump_root: Path, course: str, class_id: str) -> Path:
    dest = dump_root / course / class_id
    dest.mkdir(parents=True, exist_ok=True)
    for p in list(raw_dir.iterdir()):
        target = dest / p.name
        if target.exists():
            target.unlink() if target.is_file() else shutil.rmtree(target)
        shutil.move(str(p), str(target))
    return dest


def mirror_vault(vault_course: Path, drive_course_dir: Path) -> None:
    dest = drive_course_dir / "notas"
    dest.mkdir(parents=True, exist_ok=True)
    subprocess.run(["rsync", "-a", "--delete", "--exclude", ".obsidian", "--exclude", ".DS_Store",
                    f"{vault_course}/", f"{dest}/"], check=True, capture_output=True)
```
Run: `uv run pytest tests/test_sync.py -q` · Expected: 2 passed.

- [ ] **Step 3: Commit**
```bash
git add pipeline/sync.py tests/test_sync.py
git commit -m "feat: move raw media to the Drive dump and mirror the vault to each course folder"
```

---

## Ola 3 (2 agentes en paralelo; requiere Ola 2 en master)

### Task 10: CLI `python -m pipeline`

**Files:** Create `pipeline/__main__.py`, `pipeline/cli_helpers.py`, `tests/test_cli.py`.
**DoD:** todos los comandos de 0.8 existen; `--help` lista 12 comandos; sin `--class` itera clases con etapa previa `ok`; cada comando marca estado `ok|blocked` y nunca re-corre una etapa `ok` sin `--force`; `status` imprime tabla por curso.

- [ ] **Step 1: tests (fallan)**
```python
# tests/test_cli.py
from typer.testing import CliRunner
from pipeline.__main__ import app
from pipeline import cli_helpers as ch, state

runner = CliRunner()

def test_help_lists_commands():
    r = runner.invoke(app, ["--help"])
    assert r.exit_code == 0
    for c in ("list-showcase", "fetch", "transcript", "frames", "prompt", "analyze", "validate", "integrate", "canvas", "sync", "status", "init-vault"):
        assert c in r.output

def test_pending_classes_selects_by_previous_stage(tmp_path, monkeypatch):
    from pipeline import config
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    a = config.class_dirs("arqui", "2026-09-30-clase-01")["state"]; b = config.class_dirs("arqui", "2026-10-07-clase-02")["state"]
    state.mark(a, "fetch", "ok"); state.mark(a, "transcript", "ok"); state.mark(b, "fetch", "ok")
    assert ch.pending_classes("arqui", "transcript") == ["2026-10-07-clase-02"]
    assert ch.pending_classes("arqui", "frames") == ["2026-09-30-clase-01"]
    assert ch.pending_classes("arqui", "transcript", force=True) == ["2026-09-30-clase-01", "2026-10-07-clase-02"]

def test_status_table(tmp_path, monkeypatch):
    from pipeline import config
    monkeypatch.setattr(config, "STATE", tmp_path / "state")
    state.set_meta(config.class_dirs("arqui", "2026-09-30-clase-01")["state"], title="t")
    state.mark(config.class_dirs("arqui", "2026-09-30-clase-01")["state"], "fetch", "blocked", error="sin VTT")
    r = runner.invoke(app, ["status", "--course", "arqui"])
    assert r.exit_code == 0 and "2026-09-30-clase-01" in r.output and "blocked" in r.output
```
Run: `uv run pytest tests/test_cli.py -q` · Expected: FAIL (ImportError).

- [ ] **Step 2: helpers**
```python
# pipeline/cli_helpers.py
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
        "duracion": st.get("duration"), "vimeo_url": st.get("vimeo_url", ""),
        "video_path": video or "", "img_rel": f"img/{class_id}",
    }


def relpath(p: Path) -> str:
    try:
        return str(p.relative_to(config.ROOT))
    except ValueError:
        return str(p)


def load_json(p: Path):
    return json.loads(p.read_text(encoding="utf-8"))
```

- [ ] **Step 3: CLI**
```python
# pipeline/__main__.py
from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import avisos, canvas, cli_helpers as ch, config, fetch as fetch_mod, frames as frames_mod, integrate, note_validate, \
    prompt_builder, runner, state, sync as sync_mod, vtt

app = typer.Typer(help="Video Course AI Helper pipeline", no_args_is_help=True)
con = Console()


def _settings():
    return config.load_settings()


def _classes(course: str, stage: str, class_id: str | None, force: bool) -> list[str]:
    if class_id:
        return [class_id]
    return ch.pending_classes(course, stage, force)


@app.command("list-showcase")
def list_showcase(course: str = typer.Option(...)):
    """List the showcase videos with the class ids they would get."""
    from .naming import assign_ids
    from .vimeo import VimeoShowcase

    c = config.course(_settings(), course)
    vids = VimeoShowcase(c.showcase_id, c.password).list_videos()
    ids = assign_ids(vids)
    for v in vids:
        con.print(f"{ids[v.video_id]}  {v.video_id}  {v.duration // 60} min  {v.title}")


@app.command()
def fetch(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"),
          subs_only: bool = False, force: bool = False):
    """Download captions (+ video unless --subs-only) for every class not fetched yet."""
    c = config.course(_settings(), course)
    for r in fetch_mod.fetch_course(c, subs_only=subs_only, only_class=class_id, force=force):
        con.print(r)


@app.command()
def transcript(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"), force: bool = False):
    s = _settings()
    for cid in _classes(course, "transcript", class_id, force):
        d = config.class_dirs(course, cid)
        v = state.load(d["state"])["stages"]["fetch"].get("vtt")
        if not v:
            state.mark(d["state"], "transcript", "blocked", error="sin VTT")
            continue
        n = vtt.convert(Path(v), d["work"] / "transcript.md", f"{course} · {cid}",
                        float(s.transcript["paragraph_seconds"]), config.glossary_path(course))
        state.mark(d["state"], "transcript", "ok", cues=n)
        con.print(f"{cid}: {n} cues -> {ch.relpath(d['work'] / 'transcript.md')}")


@app.command()
def frames(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"), force: bool = False):
    s = _settings()
    for cid in _classes(course, "frames", class_id, force):
        d = config.class_dirs(course, cid)
        video = state.load(d["state"])["stages"]["fetch"].get("video")
        if not video:
            state.mark(d["state"], "frames", "blocked", error="sin video (corré fetch sin --subs-only)")
            continue
        try:
            segs = frames_mod.process(Path(video), d["work"], d["img"], cid, s.frames)
        except Exception as e:  # ffmpeg/tesseract failures are reported, not hidden
            state.mark(d["state"], "frames", "blocked", error=str(e)[:500])
            continue
        kept = sum(1 for x in segs if x.keep)
        state.mark(d["state"], "frames", "ok", segments=len(segs), kept=kept)
        con.print(f"{cid}: {len(segs)} segments, {kept} kept -> {ch.relpath(d['img'])}")


@app.command()
def prompt(course: str = typer.Option(...), class_id: str = typer.Option(..., "--class")):
    """Build work/<course>/<class>/analysis-prompt.md and avisos-excerpts.md (no LLM call)."""
    s = _settings()
    c = config.course(s, course)
    d = config.class_dirs(course, class_id)
    meta = ch.meta_for(c, class_id)
    p = prompt_builder.build_analysis_prompt(meta, d["work"] / "transcript.md", d["work"] / "frames.json",
                                             d["note"], d["work"] / "temas-candidatos.json", meta["img_rel"])
    (d["work"] / "analysis-prompt.md").write_text(p, encoding="utf-8")
    hits = avisos.excerpts(avisos.read_transcript(d["work"] / "transcript.md"), s.avisos_keywords)
    (d["work"] / "avisos-excerpts.md").write_text(avisos.to_markdown(hits), encoding="utf-8")
    con.print(f"{class_id}: prompt {len(p)} chars, {len(hits)} fragmentos de avisos -> {ch.relpath(d['work'])}")


@app.command()
def analyze(course: str = typer.Option(...), class_id: str = typer.Option(..., "--class"),
            runner_name: str = typer.Option("agent", "--runner"), budget: float = 3.0, force: bool = False):
    """runner=agent: only builds the prompt (dispatch an in-session subagent). runner=claude-p: runs headless."""
    d = config.class_dirs(course, class_id)
    if state.is_done(d["state"], "analyze") and not force:
        con.print(f"{class_id}: analyze ya ok (usar --force)")
        return
    prompt(course, class_id)
    if runner_name == "agent":
        con.print(f"Prompt listo: {ch.relpath(d['work'] / 'analysis-prompt.md')} -> despachar agente analista-clase (sonnet)")
        return
    try:
        r = runner.run_claude(d["work"] / "analysis-prompt.md", "sonnet", budget)
    except Exception as e:
        state.mark(d["state"], "analyze", "blocked", error=str(e)[:500])
        raise typer.Exit(1)
    if not d["note"].exists():
        state.mark(d["state"], "analyze", "blocked", error="claude -p terminó sin escribir la nota", **r)
        raise typer.Exit(1)
    state.mark(d["state"], "analyze", "ok", runner="claude-p", **r)
    con.print(f"{class_id}: nota escrita, costo {r['cost_usd']}")


@app.command()
def validate(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"), force: bool = False):
    for cid in _classes(course, "validate", class_id, force):
        d = config.class_dirs(course, cid)
        if not d["note"].exists():
            state.mark(d["state"], "validate", "blocked", errors=["nota inexistente"])
            continue
        errs = note_validate.validate(d["note"], config.VAULT)
        state.mark(d["state"], "validate", "ok" if not errs else "blocked", errors=errs)
        con.print(f"{cid}: {'OK' if not errs else errs}")


@app.command()
def integrate_cmd(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"), force: bool = False):
    s = _settings()
    c = config.course(s, course)
    vc = config.VAULT / course
    for cid in _classes(course, "integrate", class_id, force):
        d = config.class_dirs(course, cid)
        cands_path = d["work"] / "temas-candidatos.json"
        if not cands_path.exists():
            state.mark(d["state"], "integrate", "blocked", error="sin temas-candidatos.json")
            continue
        counts = {"created": 0, "updated": 0, "unchanged": 0}
        for cand in ch.load_json(cands_path):
            counts[integrate.upsert_tema(vc, course, cand, cid)] += 1
        state.mark(d["state"], "integrate", "ok", **counts)
        con.print(f"{cid}: {counts}")
    integrate.regen_moc(vc, course, c.full_name)
    integrate.regen_avisos(vc, course)
    integrate.regen_calendario(config.VAULT, list(s.courses))


app.command("integrate")(integrate_cmd)


@app.command("canvas")
def canvas_cmd(course: str = typer.Option(...)):
    vc = config.VAULT / course
    moc = vc / f"MOC-{course}.md"
    names = {p.stem: p.relative_to(config.VAULT).as_posix() for p in config.VAULT.rglob("*.md")}
    data = canvas.to_canvas(config.course(_settings(), course).full_name, canvas.outline(moc.read_text(encoding="utf-8")), names.get)
    out = vc / f"MOC-{course}.canvas"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    con.print(f"{ch.relpath(out)}: {len(data['nodes'])} nodos")


@app.command("sync")
def sync_cmd(course: str = typer.Option(...), class_id: str | None = typer.Option(None, "--class"), force: bool = False):
    s = _settings()
    c = config.course(s, course)
    if not s.drive_root.exists():
        raise typer.BadParameter(f"DRIVE_ROOT no existe: {s.drive_root}")
    for cid in _classes(course, "sync", class_id, force):
        d = config.class_dirs(course, cid)
        if d["raw"].exists():
            sync_mod.move_raw(d["raw"], s.drive_root / "_clases-dump", course, cid)
        state.mark(d["state"], "sync", "ok")
        con.print(f"{cid}: crudo movido a _clases-dump")
    sync_mod.mirror_vault(config.VAULT / course, s.drive_root / c.drive_folder)
    con.print(f"vault/{course} -> {c.drive_folder}/notas/")


@app.command()
def status(course: str | None = typer.Option(None)):
    courses = [course] if course else sorted(p.name for p in config.STATE.glob("*") if p.is_dir())
    for cname in courses:
        t = Table(title=cname)
        t.add_column("clase")
        for s in state.STAGES:
            t.add_column(s[:5])
        for st in state.all_states(config.STATE, cname):
            row = [st.get("class_id", "?")]
            for s in state.STAGES:
                x = st["stages"].get(s, {})
                row.append({"ok": "ok", "blocked": "blocked"}.get(x.get("status"), "·"))
            t.add_row(*row)
        con.print(t)


@app.command("init-vault")
def init_vault():
    s = _settings()
    for slug in s.courses:
        for sub in ("clases/img", "temas"):
            (config.VAULT / slug / sub).mkdir(parents=True, exist_ok=True)
    moc = config.VAULT / "00-MOC-2026.md"
    if not moc.exists():
        moc.write_text("# 2026 — cursos\n\n" + "".join(f"- [[MOC-{slug}]] — {c.full_name}\n" for slug, c in s.courses.items()),
                       encoding="utf-8")
    con.print(f"vault listo en {config.VAULT} (abrir esa carpeta como bóveda en Obsidian)")


if __name__ == "__main__":
    app()
```
Run: `uv run pytest -q` · Expected: todo verde. `uv run python -m pipeline --help` · Expected: 12 comandos.

- [ ] **Step 4: validación de punta a punta sin LLM (clase 01 de arqui)**
Run: `uv run python -m pipeline fetch --course arqui --class <id-de-la-clase-01> && uv run python -m pipeline transcript --course arqui && uv run python -m pipeline frames --course arqui --class <id> && uv run python -m pipeline prompt --course arqui --class <id> && uv run python -m pipeline status --course arqui`
Expected: `transcript.md` con `[hh:mm:ss]`, `frames.json` con `kept` > 0, imágenes en `vault/arqui/clases/img/<id>/`, `analysis-prompt.md` < 200K chars. Registrar en `_meta/PROGRESS.md` cuántos frames quedaron y cuántos son speaker (ajustar `min_words`/`phash_distance_same` si hace falta; decisión en DECISIONES).

- [ ] **Step 5: Commit**
```bash
git add pipeline/__main__.py pipeline/cli_helpers.py tests/test_cli.py
git commit -m "feat: typer CLI orchestrating the per-class pipeline with resumable state"
```

### Task 11: Prompts de los agentes, agentes de sesión y skills del proyecto

**Files:** Create/replace `prompts/analista-clase.md`, `prompts/verificador-avisos.md`, `prompts/integrador-vault.md`; Modify `.claude/agents/analista-clase.md`, `.claude/agents/verificador-avisos.md`, `.claude/agents/integrador-vault.md` (apuntan a los prompts); Create `.claude/skills/vch-pipeline/SKILL.md` (ya existe un borrador: completarlo con los comandos reales del CLI).
**DoD:** cada prompt fija: rol, entradas, salidas exactas (rutas/contratos 0.6–0.7), reglas de calidad y formato de respuesta. Prueba: `uv run python -m pipeline prompt --course arqui --class <id>` produce un prompt cuyo encabezado es el rol completo.

- [ ] **Step 1: `prompts/analista-clase.md`**
```markdown
# Rol: analista de clase
Sos ayudante de cátedra. Escribís la nota definitiva de UNA clase universitaria a partir del transcript (VTT automático de Vimeo, con errores de reconocimiento) y de los frames disponibles. Español rioplatense; términos técnicos en inglés cuando así se usan en la materia.

## Reglas
1. Usá SOLO el transcript y los frames de este prompt. No inventes contenido ni fechas. Si algo es ambiguo, va en "Dudas / a verificar".
2. Respetá la plantilla: frontmatter completo, las 10 secciones H2 en ese orden, sección vacía = `—`.
3. Cada afirmación importante lleva timestamp `[hh:mm:ss]` tomado del transcript. Las citas textuales van entre comillas con timestamp.
4. ⚠️ Avisos del profesor: TODO lo que diga sobre parciales, exámenes, entregas, obligatorios, fechas, plazos, rúbricas, reglas de evaluación, qué "va a estar en el examen", recomendaciones de estudio, cambios de cronograma. Formato: `- <aviso> — "<cita>" [hh:mm:ss]`. Si menciona una fecha, escribila en formato `dd/mm`.
5. Imágenes: elegí los frames que muestran slides, código, diagramas o demos relevantes (abrilos con Read si dudás). Embebé cada uno como `![](img/<class_id>/<archivo>)` seguido de una línea "Qué muestra: … [hh:mm:ss]". No embebas frames de la cámara del profesor.
6. Desarrollo por tema: un H3 por tema, en orden cronológico, explicado como para estudiar sin ver el video (definiciones, razonamiento del profesor, ejemplos). Índice de temas: lista `- [hh:mm:ss] [[slug-del-tema]] — título`.
7. Temas candidatos: escribí `temas-candidatos.json` con la lista de temas (contrato: `[{"slug","titulo","resumen" (≤5 líneas),"timestamps":["hh:mm:ss"],"relacionados":["título"]}]`). Slugs en minúsculas con guiones, sin acentos.
8. Escribí los dos archivos en las rutas indicadas en "Salidas obligatorias". Respondé SOLO con: rutas + resumen ≤3 líneas + `OK` o `BLOQUEADO <motivo>`.
```

- [ ] **Step 2: `prompts/verificador-avisos.md`**
```markdown
# Rol: verificador de avisos
Sos el revisor final. Tu única tarea es encontrar avisos del profesor (parciales, exámenes, entregas, fechas, reglas, "esto va al examen") que falten o estén mal en la sección "⚠️ Avisos del profesor" de la nota. No reescribís la nota.

## Procedimiento
1. Leé la sección ⚠️ de la nota indicada (solo esa sección).
2. Recorré los fragmentos del transcript de abajo (prefiltrados por keywords, ±60 s de contexto).
3. Para cada aviso que falte, esté mal fechado o sea ambiguo, escribí: `- [hh:mm:ss] FALTA|CORREGIR|AMBIGUO — <qué dice la nota> → <qué dijo el profesor> — "<cita>"`. Distinguí "dato firme" de "lo insinuó".
4. Escribí el informe en la ruta indicada en "Salida" con el encabezado `# Revisión de avisos · <class_id>` y, al final, una línea `Faltantes: N · Correcciones: N · Ambiguos: N`.
5. Respondé SOLO con esa línea final + la ruta + `OK`.
```

- [ ] **Step 3: `prompts/integrador-vault.md`**
```markdown
# Rol: integrador del vault
Organizás el mapa de contenido (MOC) de un curso en Obsidian después de que el script creó/enriqueció las notas de `temas/`.

## Procedimiento
1. Entradas: `vault/<curso>/MOC-<curso>.md` (la parte generada entre `<!-- generated:start -->` y `<!-- generated:end -->` lista TODOS los temas y clases; no la edites) y las notas de `vault/<curso>/temas/*.md` que necesites (leé solo las que vas a ubicar).
2. En la sección `## Mapa` (arriba de los marcadores) armá un outline jerárquico con `- ` y dos espacios por nivel: unidades/ejes del curso → subtemas → `[[slug]]`. Todo tema de la lista generada debe aparecer exactamente una vez en el outline. Las hojas son wikilinks a temas; los niveles superiores son texto.
3. Si dos temas son claramente el mismo concepto con nombres distintos, NO los fusiones: listalos en tu respuesta como "posible duplicado" para arbitraje.
4. Respondé SOLO con: cantidad de temas ubicados, posibles duplicados, ruta del MOC, `OK`.
```

- [ ] **Step 4: agentes de sesión** (reemplazar el cuerpo de cada uno por 3 líneas; el prompt real lo arma el CLI y viaja en el mensaje del orquestador)
```markdown
---
name: analista-clase
description: Escribe la nota .md completa de UNA clase + temas-candidatos.json a partir del prompt generado por `pipeline prompt`.
tools: Read, Write
model: sonnet
maxTurns: 15
---
El orquestador pega en tu tarea el contenido de `work/<curso>/<clase>/analysis-prompt.md` (rol, metadatos, salidas, plantilla, frames, transcript). Seguilo al pie de la letra. No leas otras clases ni documentos del repo.
```
```markdown
---
name: verificador-avisos
description: Revisa (recall) la sección ⚠️ Avisos de una nota contra los fragmentos del transcript. Único agente en opus.
tools: Read, Write
model: opus
maxTurns: 10
---
El orquestador pega en tu tarea el prompt generado por `prompt_builder.build_avisos_prompt` (rol, metadatos, rutas, fragmentos). Seguilo al pie de la letra; no edites la nota.
```
```markdown
---
name: integrador-vault
description: Organiza el outline jerárquico del MOC de un curso en Obsidian sobre los temas ya creados por `pipeline integrate`.
tools: Read, Write, Glob
model: sonnet
maxTurns: 20
---
El orquestador pega en tu tarea `prompts/integrador-vault.md` + el curso. Editá solo `vault/<curso>/MOC-<curso>.md` por encima de los marcadores generados.
```

- [ ] **Step 5: Commit**
```bash
git add prompts/analista-clase.md prompts/verificador-avisos.md prompts/integrador-vault.md .claude/agents/analista-clase.md .claude/agents/verificador-avisos.md .claude/agents/integrador-vault.md .claude/skills/vch-pipeline/SKILL.md
git commit -m "feat: agent prompts, session agents and project skill for the class pipeline"
```

---

## Ola 4 (secuencial con Robert; luego tandas)

### Task 12: Pilot end-to-end (1 clase de arqui) — checkpoint humano

**DoD:** nota de una clase validada por `validate` sin errores, revisada por `verificador-avisos`, aprobada por Robert (nivel de detalle, imágenes, avisos). Decisiones de ajuste en `_meta/DECISIONES.md`.

- [ ] 1. `uv run python -m pipeline fetch --course arqui --class <id>` (con video) → `transcript` → `frames` → `prompt`.
- [ ] 2. Despachar `analista-clase` (sonnet) con el contenido de `analysis-prompt.md`. Al volver: `uv run python -m pipeline validate --course arqui --class <id>`; si hay errores, pasárselos al mismo agente para corregir (una vez).
- [ ] 3. Generar prompt de avisos: `uv run python -c "from pipeline import prompt_builder as pb, config, cli_helpers as ch; c=config.course(config.load_settings(),'arqui'); d=config.class_dirs('arqui','<id>'); print(pb.build_avisos_prompt(ch.meta_for(c,'<id>'), d['work']/'avisos-excerpts.md', d['note'], d['work']/'avisos-review.md'))" > work/arqui/<id>/avisos-prompt.md` y despachar `verificador-avisos` (opus). Aplicar correcciones a la nota con el analista (sonnet) si hay faltantes.
- [ ] 4. `uv run python -m pipeline integrate --course arqui && uv run python -m pipeline canvas --course arqui` → abrir `vault/` en Obsidian; verificar que la nota, las imágenes, los wikilinks y el canvas se ven.
- [ ] 5. Robert revisa. Ajustes a plantilla/prompts/umbrales → DECISIONES.md → re-correr solo esta clase con `--force`.
- [ ] 6. `_meta/PROGRESS.md`: F2 ✅ con costo real de la clase (de `state`). Commit de cualquier cambio en `prompts/`, `templates/`, `config/` (`git add` de esos archivos): `chore: pilot adjustments after first class review`.

### Task 13: Tandas (resto de clases) — hasta 4 agentes

**DoD:** 45 clases con `analyze`, `validate`, `integrate` en `ok` (o `blocked` documentado en PROGRESS.md con motivo); avisos verificados por curso; MOC organizado por `integrador-vault`; canvas generado; costo total registrado.

- [ ] 1. `fetch` completo por curso en background (video + vtt), en el orden que Robert fije (curso con evaluación más cercana primero). `transcript` y `frames` para todo (script, local).
- [ ] 2. Tandas de 4 clases: `prompt` ×4 → despachar 4 `analista-clase` en paralelo → `validate` → correcciones (1 reintento) → `_meta/PROGRESS.md` (tabla curso × clase × estado × costo). Reportar a Robert a la mitad de cada curso.
- [ ] 3. Al cerrar un curso: `verificador-avisos` (opus) sobre todas sus clases en un solo despacho por clase pero secuencial (es el único costo opus); aplicar faltantes; `integrate`; despachar `integrador-vault` (sonnet) para el outline del MOC; `canvas`; `sync`.
- [ ] 4. Alarma de presupuesto: si una tanda de 4 supera 5 USD (suma de `cost_usd` en `state`), parar y revisar prompts antes de seguir.

### Task 14: Rutina semanal `/nueva-clase` y cierre

**Files:** Modify `.claude/commands/nueva-clase.md`, `.claude/skills/vch-pipeline/SKILL.md`, `CLAUDE.md`, `_meta/PROGRESS.md`.
**DoD:** con un video nuevo publicado, `/nueva-clase <curso>` deja la nota validada, integrada y sincronizada a Drive sin intervención, o reporta exactamente dónde se bloqueó.

- [ ] 1. `.claude/commands/nueva-clase.md`:
```markdown
Argumento: `$ARGUMENTS` = slug del curso (arqui|negsoft|dbpt|isa2).
1. `uv run python -m pipeline fetch --course $ARGUMENTS` (incremental: solo clases nuevas). Si no hay nuevas, decirlo y terminar.
2. `uv run python -m pipeline transcript --course $ARGUMENTS && uv run python -m pipeline frames --course $ARGUMENTS`.
3. Por cada clase nueva (ver `status`): `uv run python -m pipeline analyze --course $ARGUMENTS --class <id> --runner claude-p --budget 3`. Si `claude -p` no está disponible o devuelve error, usar `--runner agent` y despachar `analista-clase` con el prompt.
4. `validate` → si falla, corregir con el analista (1 vez) → generar prompt de avisos y despachar `verificador-avisos` (opus) → aplicar faltantes → `integrate` → `canvas` → `sync`.
5. Reportar: ruta de la nota, avisos nuevos (copiar la sección ⚠️), costo (`state`), y si algo quedó `blocked`, el error exacto. Actualizar `_meta/PROGRESS.md`.
```
- [ ] 2. `CLAUDE.md`: línea "Después de cada clase nueva: abrir Claude Code en este repo y correr `/nueva-clase <curso>`".
- [ ] 3. Commit: `git add .claude/commands/nueva-clase.md .claude/skills/vch-pipeline/SKILL.md CLAUDE.md _meta/PROGRESS.md && git commit -m "feat: weekly new-class routine"`.

---

## Self-review (hecho al escribir el plan)
- **Cobertura del spec:** retrieval (T2, T6), transcript (T3), frames (T4), análisis (T7, T11, T12), validación mecánica (T5, T10) y de avisos (T7, T11, T12), organización/mind map (T8, T10 canvas, T11 integrador), sync/backup (T9, T10), rutina semanal (T14), estado idempotente (T1, T10). Sin ASR local (decisión de Robert). Clasificador visual LLM de frames: fuera de v1 (heurística OCR en T4); si el pilot muestra frames de cámara embebidos, agregar como T4b.
- **Placeholders:** ninguno; `<id>` en T10/T12 es el `class_id` real que imprime `list-showcase`.
- **Consistencia de nombres:** `config.class_dirs` (raw/work/state/note/img/vault_course) y `state.mark/is_done/next_pending` se usan igual en T6, T10; `frames.process` firma igual en T4 y T10; `prompt_builder.build_analysis_prompt/build_avisos_prompt` igual en T7, T10, T12; `integrate.upsert_tema/regen_moc/regen_avisos/regen_calendario` igual en T8, T10.
