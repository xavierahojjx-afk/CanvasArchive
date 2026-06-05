from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import MANIFESTS_DIR


def manifest_path(course_id: int | str) -> Path:
    return MANIFESTS_DIR / f"{course_id}.json"


def empty_manifest(course_id: int | str) -> dict[str, Any]:
    return {
        "course_id": int(course_id),
        "course_code": "",
        "course_name": "",
        "category": "",
        "home_page": None,
        "syllabus": None,
        "files": [],
        "pages": [],
        "links": [],
        "assignments": [],
        "discussions": [],
        "submissions": [],
    }


def load_manifest(course_id: int | str) -> dict[str, Any]:
    path = manifest_path(course_id)
    if not path.exists():
        return empty_manifest(course_id)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    for key in ("files", "pages", "links", "assignments", "discussions", "submissions"):
        data.setdefault(key, [])
    return data


def save_manifest(course_id: int | str, data: dict[str, Any]) -> None:
    """Atomic write: tmp file then rename, so a crash mid-write can't corrupt."""
    path = manifest_path(course_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
        raise


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
