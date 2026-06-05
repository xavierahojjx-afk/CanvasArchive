from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from rich.console import Console
from tqdm import tqdm

from .canvas_client import canvas_retry, get_canvas
from .config import LOGS_DIR
from .discover import read_included_courses
from .files import _course_folder, _extract_file_ids
from .manifest import load_manifest, now_iso, save_manifest
from .rendering import (
    WEASYPRINT_OK,
    render_assignment_html,
    weasyprint_error,
    write_pdf_or_html,
)
from .utils import get_error_logger, sanitize_filename


@canvas_retry
def _get_course(canvas, course_id: int):
    return canvas.get_course(course_id)


@canvas_retry
def _list_assignments(course):
    return list(course.get_assignments(include=["submission"], per_page=100))


@canvas_retry
def _get_submission(assignment):
    return assignment.get_submission("self", include=["submission_comments"])


@canvas_retry
def _get_file(canvas, file_id: int):
    return canvas.get_file(file_id)


def _download_to(file_obj, dest_path: Path) -> None:
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest_path.with_name(dest_path.name + ".part")
    try:
        file_obj.download(str(tmp))
        os.replace(tmp, dest_path)
    except Exception:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
        raise


def _to_dict_safe(obj: Any) -> dict[str, Any]:
    """Convert canvasapi attribute objects to dicts; pass through dicts."""
    if isinstance(obj, dict):
        return obj
    if hasattr(obj, "__dict__"):
        return {k: v for k, v in obj.__dict__.items() if not k.startswith("_")}
    return {}


def _list_to_dicts(items: Any) -> list[dict[str, Any]]:
    if not items:
        return []
    return [_to_dict_safe(x) for x in items]


def _archive_course(
    row: dict[str, str],
    canvas,
    logger: logging.Logger,
    console: Console,
    *,
    force: bool,
) -> tuple[int, int, int]:
    course_id = int(row["course_id"])
    course_code = row["course_code"]
    course_name = row["name"]
    category = row.get("category", "")

    console.print(f"\n[cyan]== {course_code}[/cyan]  [dim]{course_name}[/dim]")
    course_dir = _course_folder(category, course_code, course_name)
    assignments_dir = course_dir / "_assignments"
    attachments_root = assignments_dir / "_instructor_attachments"

    manifest = load_manifest(course_id)
    manifest["course_id"] = course_id
    manifest["course_code"] = course_code
    manifest["course_name"] = course_name
    manifest["category"] = category

    try:
        course = _get_course(canvas, course_id)
        assignments = _list_assignments(course)
    except Exception as exc:
        logger.error(f"{course_code}: list assignments failed: {exc}")
        console.print(f"  [red]list assignments failed: {exc}[/red]")
        return 0, 0, 1

    existing_by_id = {a.get("assignment_id"): a for a in manifest.get("assignments", [])}

    rendered = skipped = errored = 0

    bar = tqdm(assignments, desc="  assignments", leave=False, unit="asn")
    for assignment in bar:
        a_id = getattr(assignment, "id", None)
        if not a_id:
            continue
        a_name = getattr(assignment, "name", f"assignment_{a_id}") or f"assignment_{a_id}"
        position = getattr(assignment, "position", 0) or 0

        if not force and a_id in existing_by_id:
            prev = existing_by_id[a_id]
            prev_path = prev.get("render_path")
            if prev_path and Path(prev_path).exists():
                skipped += 1
                continue

        try:
            try:
                submission = _get_submission(assignment)
                sub_dict = {
                    "score": getattr(submission, "score", None),
                    "body": getattr(submission, "body", None),
                    "submitted_at": getattr(submission, "submitted_at", None),
                    "workflow_state": getattr(submission, "workflow_state", None),
                    "submission_comments": _list_to_dicts(
                        getattr(submission, "submission_comments", []) or []
                    ),
                    "attachments": _list_to_dicts(
                        getattr(submission, "attachments", []) or []
                    ),
                }
            except Exception as exc:
                logger.error(f"{course_code}: get_submission for {a_id} ({a_name}): {exc}")
                sub_dict = {
                    "score": None, "body": "", "submitted_at": None,
                    "workflow_state": "unfetched", "submission_comments": [],
                    "attachments": [],
                }

            a_dict = {
                "name": a_name,
                "description": getattr(assignment, "description", None),
                "due_at": getattr(assignment, "due_at", None),
                "points_possible": getattr(assignment, "points_possible", None),
            }

            # Download instructor-attached files embedded in the description HTML
            desc_html = a_dict["description"] or ""
            file_ids = _extract_file_ids(desc_html)
            inst_attachments_meta: list[dict[str, Any]] = []
            for file_id in file_ids:
                try:
                    f = _get_file(canvas, file_id)
                    filename = sanitize_filename(
                        getattr(f, "display_name", "")
                        or getattr(f, "filename", "")
                        or f"file_{file_id}"
                    )
                    a_subdir = attachments_root / sanitize_filename(
                        f"{position:02d} {a_name}", max_length=120
                    )
                    dest = a_subdir / filename
                    if not dest.exists():
                        _download_to(f, dest)
                    inst_attachments_meta.append({
                        "display_name": filename,
                        "file_id": file_id,
                    })
                except Exception as exc:
                    logger.error(
                        f"{course_code}: assignment {a_id} ({a_name}): "
                        f"instructor attachment {file_id}: {exc}"
                    )

            html_str = render_assignment_html(
                course_code=course_code,
                course_name=course_name,
                assignment=a_dict,
                submission=sub_dict,
                assignment_attachments=inst_attachments_meta,
                submission_attachments=sub_dict.get("attachments", []),
            )

            base_name = sanitize_filename(f"{position:02d} {a_name}", max_length=180)
            dest_pdf = assignments_dir / f"{base_name}.pdf"
            out_path, kind = write_pdf_or_html(html_str, dest_pdf)

            manifest["assignments"] = [
                a for a in manifest["assignments"] if a.get("assignment_id") != a_id
            ]
            manifest["assignments"].append({
                "assignment_id": a_id,
                "name": a_name,
                "position": position,
                "due_at": a_dict.get("due_at"),
                "score": sub_dict.get("score"),
                "points_possible": a_dict.get("points_possible"),
                "render_path": str(out_path),
                "render_kind": kind,
                "instructor_attachments": inst_attachments_meta,
                "rendered_at": now_iso(),
            })
            save_manifest(course_id, manifest)
            rendered += 1
        except Exception as exc:
            logger.error(
                f"{course_code}: assignment {a_id} ({a_name}): render failed: {exc}"
            )
            errored += 1
    bar.close()

    console.print(
        f"  [green]{rendered} rendered[/green]  "
        f"[dim]{skipped} skipped[/dim]  "
        f"[yellow]{errored} errors[/yellow]"
    )
    return rendered, skipped, errored


def run(
    course_id: int | None = None,
    category: str | None = None,
    force: bool = False,
    dry_run: bool = False,
) -> int:
    console = Console()
    logger = get_error_logger("canvas_export.assignments")
    canvas = get_canvas()

    try:
        rows = read_included_courses()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    if course_id is not None:
        rows = [r for r in rows if str(r["course_id"]) == str(course_id)]
        if not rows:
            console.print(f"[red]Course {course_id} not in inventory[/red]")
            return 1

    if category is not None:
        cat = category.strip().lower()
        rows = [r for r in rows if r.get("category", "").strip().lower() == cat]
        if not rows:
            console.print(f"[red]No included courses with category '{category}'[/red]")
            return 1

    if dry_run:
        console.print(f"[yellow]Dry run — would process {len(rows)} course(s)[/yellow]")
        return 0

    if WEASYPRINT_OK:
        console.print("[green]weasyprint available — assignments will render to PDF[/green]")
    else:
        err = weasyprint_error() or "unknown"
        console.print(
            f"[yellow]weasyprint NOT available ({err}).[/yellow]\n"
            "[yellow]Assignments will be saved as .html instead of .pdf. "
            "Same content, just open in your browser.[/yellow]"
        )

    console.print(
        f"[cyan]Phase 3 (assignments): processing {len(rows)} course(s)…[/cyan]"
    )
    tr = ts = te = 0
    for row in rows:
        r, s, e = _archive_course(row, canvas, logger, console, force=force)
        tr += r
        ts += s
        te += e

    console.print(
        f"\n[bold]Done.[/bold]  [green]{tr} rendered[/green]  "
        f"[dim]{ts} skipped[/dim]  [yellow]{te} errors[/yellow]"
    )
    if te:
        console.print(f"See [bold]{LOGS_DIR / 'errors.log'}[/bold] for details.")
    return 0 if te == 0 else 2
