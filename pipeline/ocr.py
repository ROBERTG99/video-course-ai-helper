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
