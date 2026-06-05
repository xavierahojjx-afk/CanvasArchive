from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

from .config import LOGS_DIR

_INVALID_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize_filename(name: str, max_length: int = 200) -> str:
    """Strip path-unsafe chars; truncate while preserving extension."""
    if not name:
        return "_unnamed"
    cleaned = _INVALID_CHARS.sub("_", name).strip().strip(".").strip()
    if not cleaned:
        return "_unnamed"
    if len(cleaned) <= max_length:
        return cleaned
    p = Path(cleaned)
    stem, ext = p.stem, p.suffix
    if len(ext) > 10 or not ext:
        return cleaned[:max_length].rstrip()
    return (stem[: max_length - len(ext)]).rstrip() + ext


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()


def get_error_logger(name: str = "canvas_export") -> logging.Logger:
    """File logger writing to logs/errors.log. Idempotent across calls."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
        handler = logging.FileHandler(LOGS_DIR / "errors.log", encoding="utf-8")
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False
    return logger
