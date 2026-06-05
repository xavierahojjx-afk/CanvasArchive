from __future__ import annotations

import csv
import logging
from collections import Counter
from typing import Any

from rich.console import Console
from rich.table import Table

from .canvas_client import canvas_retry, get_canvas
from .config import COURSE_INVENTORY_CSV

logger = logging.getLogger(__name__)

CSV_HEADERS = [
    "course_id",
    "course_code",
    "name",
    "term",
    "enrollment_state",
    "workflow_state",
    "start_at",
    "end_at",
    "include",
    "category",
]


@canvas_retry
def _fetch_courses() -> list[Any]:
    canvas = get_canvas()
    paginated = canvas.get_courses(
        enrollment_state=["active", "completed"],
        state=["unpublished", "available", "completed"],
        include=["term", "enrollments"],
        per_page=100,
    )
    return list(paginated)


def _extract_term_name(course: Any) -> str:
    term = getattr(course, "term", None)
    if not term:
        return ""
    if isinstance(term, dict):
        return term.get("name", "") or ""
    return getattr(term, "name", "") or ""


def _extract_enrollment_states(course: Any) -> str:
    enrollments = getattr(course, "enrollments", None) or []
    states = sorted({
        e.get("enrollment_state", "")
        for e in enrollments
        if isinstance(e, dict) and e.get("enrollment_state")
    })
    return ",".join(states)


def _row_for(course: Any) -> dict[str, Any]:
    return {
        "course_id": getattr(course, "id", ""),
        "course_code": getattr(course, "course_code", "") or "",
        "name": getattr(course, "name", "") or "",
        "term": _extract_term_name(course),
        "enrollment_state": _extract_enrollment_states(course),
        "workflow_state": getattr(course, "workflow_state", "") or "",
        "start_at": getattr(course, "start_at", "") or "",
        "end_at": getattr(course, "end_at", "") or "",
        "include": "TRUE",
        "category": "",
    }


def _read_existing_edits() -> dict[str, dict[str, str]]:
    """Preserve user edits (include, category) across re-runs."""
    if not COURSE_INVENTORY_CSV.exists():
        return {}
    out: dict[str, dict[str, str]] = {}
    with COURSE_INVENTORY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = row.get("course_id", "")
            if cid:
                out[str(cid)] = {
                    "include": row.get("include", "TRUE"),
                    "category": row.get("category", ""),
                }
    return out


def read_included_courses() -> list[dict[str, str]]:
    """Public helper for downstream phases: returns rows where include != FALSE."""
    if not COURSE_INVENTORY_CSV.exists():
        raise FileNotFoundError(
            f"{COURSE_INVENTORY_CSV} not found — run `discover` first."
        )
    with COURSE_INVENTORY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [row for row in reader if row.get("include", "TRUE").strip().upper() != "FALSE"]


def _write_csv(rows: list[dict[str, Any]]) -> None:
    COURSE_INVENTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with COURSE_INVENTORY_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    console = Console()
    console.print("[cyan]Phase 1: discovering courses…[/cyan]")

    try:
        courses = _fetch_courses()
    except Exception as exc:
        console.print(f"[red]Failed to fetch courses:[/red] {exc}")
        return 1

    rows = [_row_for(c) for c in courses]
    rows.sort(key=lambda r: (r["start_at"] or "", r["term"] or "", r["course_code"] or ""))

    existing = _read_existing_edits()
    if existing:
        preserved_include = 0
        preserved_category = 0
        for r in rows:
            cid = str(r["course_id"])
            if cid in existing:
                prev = existing[cid]
                if prev["include"] != "TRUE":
                    r["include"] = prev["include"]
                    preserved_include += 1
                if prev["category"]:
                    r["category"] = prev["category"]
                    preserved_category += 1
        if preserved_include or preserved_category:
            console.print(
                f"[dim]Preserved {preserved_include} include= edits and "
                f"{preserved_category} category values from prior run[/dim]"
            )

    _write_csv(rows)

    included_rows = [r for r in rows if r["include"] != "FALSE"]
    table = Table(title=f"Included courses by category ({len(included_rows)} of {len(rows)})")
    table.add_column("category", style="cyan")
    table.add_column("count", justify="right")
    by_cat = Counter(r["category"] or "(uncategorized)" for r in included_rows)
    for cat, n in sorted(by_cat.items()):
        table.add_row(cat, str(n))
    console.print(table)

    console.print(
        f"\nWrote [bold]{COURSE_INVENTORY_CSV}[/bold]\n"
        "Review the CSV, set [yellow]include = FALSE[/yellow] for any course to skip, "
        "then proceed to Phase 2."
    )
    return 0
