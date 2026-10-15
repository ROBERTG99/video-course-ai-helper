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


def note_name(slug: str, class_id: str) -> str:
    """Vault basename of a class note: `<curso>-<class_id>` (class ids repeat across courses; basenames must not)."""
    return f"{slug}-{class_id}"


def class_dirs(slug: str, class_id: str) -> dict[str, Path]:
    return {
        "raw": RAW / slug / class_id,
        "work": WORK / slug / class_id,
        "state": STATE / slug / f"{class_id}.json",
        "note": VAULT / slug / "clases" / f"{note_name(slug, class_id)}.md",
        "img": VAULT / slug / "clases" / "img" / class_id,
        "vault_course": VAULT / slug,
    }


def glossary_path(slug: str) -> Path:
    return CONFIG / f"glossary-{slug}.txt"
