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
    """Public helper for downstream phases: returns rows where include != FALSE.

    Any course left without a category automatically falls back to its Canvas
    term, so folders mirror Canvas out of the box with no CSV editing. This is
    the single place the term fallback is applied, so every phase (files,
    assignments, recordings, submissions) gets it for free.
    """
    if not COURSE_INVENTORY_CSV.exists():
        raise FileNotFoundError(
            f"{COURSE_INVENTORY_CSV} not found — run `discover` first."
        )
    with COURSE_INVENTORY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = [row for row in reader if row.get("include", "TRUE").strip().upper() != "FALSE"]
    for row in rows:
        if not row.get("category", "").strip():
            row["category"] = row.get("term", "").strip()
    return rows


def _read_all_rows() -> list[dict[str, str]]:
    """Read every row from the inventory CSV verbatim, preserving order."""
    with COURSE_INVENTORY_CSV.open("r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        return [dict(row) for row in reader]


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
    # Blank category falls back to the Canvas term (see read_included_courses).
    by_cat = Counter((r["category"] or r["term"]) or "(uncategorized)" for r in included_rows)
    for cat, n in sorted(by_cat.items()):
        table.add_row(cat, str(n))
    console.print(table)

    console.print(
        f"\nWrote [bold]{COURSE_INVENTORY_CSV}[/bold]\n"
        "By default each course is filed under its [cyan]Canvas term[/cyan] — "
        "you don't need to edit anything.\n"
        "To assign your own topic categories or skip courses, run "
        "[yellow]python -m canvas_export categorize[/yellow] "
        "(no spreadsheet editing needed)."
    )
    return 0


def _effective_category(row: dict[str, str]) -> str:
    """The folder a course will use: its category, else its term, else a default."""
    return row.get("category", "").strip() or row.get("term", "").strip() or "Uncategorized"


def categorize() -> int:
    """Interactively review/assign categories in the terminal — no CSV editing.

    Shows every course that will be archived, then optionally walks them
    one-by-one so the user can set a custom topic, reset to the term default,
    or exclude a course. Writes the choices back to the inventory CSV.
    """
    console = Console()

    if not COURSE_INVENTORY_CSV.exists():
        console.print(
            f"[red]{COURSE_INVENTORY_CSV} not found[/red] — run "
            "[yellow]python -m canvas_export discover[/yellow] first."
        )
        return 1

    rows = _read_all_rows()
    # included holds references into `rows`, so edits here are written back below.
    included = [r for r in rows if r.get("include", "TRUE").strip().upper() != "FALSE"]
    if not included:
        console.print("[yellow]No included courses found in the inventory.[/yellow]")
        return 0

    table = Table(title=f"Courses to be archived ({len(included)})")
    table.add_column("#", justify="right", style="dim")
    table.add_column("course", style="bold")
    table.add_column("term")
    table.add_column("will use folder", style="cyan")
    for i, r in enumerate(included, 1):
        course = f"{r.get('course_code', '')} - {r.get('name', '')}".strip(" -")
        table.add_row(str(i), course, r.get("term", "") or "(none)", _effective_category(r))
    console.print(table)

    console.print(
        "\nBy default each course is filed under its [cyan]Canvas term[/cyan] "
        "(the 'will use folder' column above) — no action needed.\n"
        "You can instead assign your own topic categories like "
        "'AI and Programming' or 'Finance and Econ'."
    )
    try:
        choice = input("Categorize courses one-by-one now? [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[green]No changes made.[/green]")
        return 0

    if choice not in ("y", "yes"):
        console.print("[green]Keeping term-based defaults. Nothing changed.[/green]")
        return 0

    console.print(
        "\nFor each course, type one of:\n"
        "  [bold]<a name>[/bold] — file it under that category/folder\n"
        "  [bold]Enter[/bold]    — keep the folder shown\n"
        "  [bold]-[/bold]        — reset to the Canvas term\n"
        "  [bold]x[/bold]        — exclude this course from the archive\n"
        "  [bold]q[/bold]        — stop here and save what you've done\n"
    )

    total = len(included)
    for i, r in enumerate(included, 1):
        term = r.get("term", "").strip()
        course = f"{r.get('course_code', '')} - {r.get('name', '')}".strip(" -")
        console.print(f"[dim][{i}/{total}][/dim] [bold]{course}[/bold]")
        console.print(f"    term: {term or '(none)'}    current folder: [cyan]{_effective_category(r)}[/cyan]")
        try:
            ans = input("    > ").strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[yellow]Stopped. Saving what you've done so far…[/yellow]")
            break

        if ans == "":
            continue
        if ans.lower() == "q":
            console.print("[yellow]Stopping. Saving what you've done so far…[/yellow]")
            break
        if ans.lower() == "x":
            r["include"] = "FALSE"
            console.print("    [yellow]excluded[/yellow]")
            continue
        if ans == "-":
            r["category"] = ""
            console.print(f"    [dim]reset to term: {term or 'Uncategorized'}[/dim]")
            continue
        r["category"] = ans
        console.print(f"    [green]set: {ans}[/green]")

    _write_csv(rows)

    still_included = [r for r in rows if r.get("include", "TRUE").strip().upper() != "FALSE"]
    summary = Table(title=f"Saved — courses by folder ({len(still_included)} included)")
    summary.add_column("folder", style="cyan")
    summary.add_column("count", justify="right")
    by_cat = Counter(_effective_category(r) for r in still_included)
    for cat, n in sorted(by_cat.items()):
        summary.add_row(cat, str(n))
    console.print(summary)
    console.print(
        f"\n[green]Saved to[/green] [bold]{COURSE_INVENTORY_CSV}[/bold]. "
        "You can re-run [yellow]categorize[/yellow] anytime to adjust."
    )
    return 0
