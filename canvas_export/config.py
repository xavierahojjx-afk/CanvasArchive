from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = PROJECT_ROOT / "downloads"
MANIFESTS_DIR = PROJECT_ROOT / "manifests"
LOGS_DIR = PROJECT_ROOT / "logs"
COURSE_INVENTORY_CSV = PROJECT_ROOT / "course_inventory.csv"
RECORDINGS_CSV = PROJECT_ROOT / "recordings_to_review.csv"
CREDENTIALS_JSON = PROJECT_ROOT / "credentials.json"
TOKEN_JSON = PROJECT_ROOT / "token.json"

DRIVE_ROOT_FOLDER_NAME = "GSB Canvas Archive"


@dataclass(frozen=True)
class Settings:
    canvas_token: str
    canvas_base_url: str


def load_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env")
    token = os.environ.get("CANVAS_TOKEN", "").strip()
    if not token:
        raise RuntimeError(
            "CANVAS_TOKEN is not set. Copy .env.example to .env and paste your token."
        )
    base_url = os.environ.get("CANVAS_BASE_URL", "https://canvas.stanford.edu").rstrip("/")
    return Settings(canvas_token=token, canvas_base_url=base_url)
