from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from .config import DOWNLOADS_DIR, PROJECT_ROOT
from .discover import read_included_courses
from .manifest import load_manifest, now_iso, save_manifest
from .utils import get_error_logger, sanitize_filename

DEFAULT_SUBMISSIONS_ROOT = PROJECT_ROOT.parent / "2026-06-03 data export submissions"


def _course_folder(category: str, course_code: str, course_name: str) -> Path:
    cat = sanitize_filename(category or "Uncategorized", max_length=100)
    folder = sanitize_filename(f"{course_code} - {course_name}", max_length=180)
    return DOWNLOADS_DIR / cat / folder


def _norm(s: str) -> str:
    """Normalize a CSV-side path segment to match how the export tool wrote it on disk."""
    return sanitize_filename((s or "").strip(), max_length=500)


def _clean_parts(parts: list[str]) -> list[str]:
    out = []
    for p in parts:
        if not p or not p.strip():
            continue
        n = _norm(p)
        if n and n != "_unnamed":
            out.append(n)
    return out


def _try_path(submissions_root: Path, parts: list[str]) -> Path | None:
    cleaned = _clean_parts(parts)
    if not cleaned:
        return None
    p = submissions_root.joinpath(*cleaned)
    try:
        next(iter(p.iterdir()))
        return p
    except StopIteration:
        return p
    except (FileNotFoundError, NotADirectoryError):
        return None


def _matches(name: str, target: str) -> bool:
    t = _norm(target)
    if not t or t == "_unnamed":
        return False
    return name == t or name.startswith(t + " ") or name.startswith(t + " - ")


def _find_top_level_match(submissions_root: Path, first_segment: str) -> Path | None:
    if not first_segment or not first_segment.strip():
        return None
    for child in submissions_root.iterdir():
        if child.is_dir() and _matches(child.name, first_segment):
            return child
    return None


def _walk_remaining(start: Path, segments: list[str]) -> Path:
    cur = start
    for seg in segments:
        if not seg or not seg.strip():
            continue
        nxt = None
        try:
            for child in cur.iterdir():
                if child.is_dir() and _matches(child.name, seg):
                    nxt = child
                    break
        except (FileNotFoundError, NotADirectoryError):
            return cur
        if nxt is None:
            return cur
        cur = nxt
    return cur


def find_source_for_course(
    submissions_root: Path, course_code: str, course_name: str
) -> Path | None:
    if not submissions_root.is_dir():
        return None

    p = _try_path(submissions_root, course_name.split("/"))
    if p is not None:
        return p

    p = _try_path(submissions_root, course_code.split("/"))
    if p is not None:
        return p

    code_parts = _clean_parts(course_code.split("/"))
    if code_parts:
        top = _find_top_level_match(submissions_root, code_parts[0])
        if top is not None:
            return _walk_remaining(top, code_parts[1:])

    name_clean = _norm(course_name)
    if name_clean and name_clean != "_unnamed":
        for child in submissions_root.iterdir():
            if child.is_dir() and child.name == name_clean:
                return child

    return None


def _build_mapping(
    submissions_root: Path, rows: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """For each included course, find source folder + count assignment-level children."""
    out: list[dict[str, Any]] = []
    for r in rows:
        course_id = int(r["course_id"])
        course_code = r["course_code"]
        course_name = r["name"]
        category = r.get("category", "")

        src = find_source_for_course(submissions_root, course_code, course_name)
        if src is None:
            out.append({
                "course_id": course_id,
                "course_code": course_code,
                "course_name": course_name,
                "category": category,
                "src": None,
                "assignments": [],
                "status": "no source",
            })
            continue

        # Children of src are the assignment folders (and any loose files)
        assignment_dirs = sorted(
            [c for c in src.iterdir() if c.is_dir()], key=lambda p: p.name.lower()
        )
        loose_files = sorted(
            [c for c in src.iterdir() if c.is_file()], key=lambda p: p.name.lower()
        )
        dest = _course_folder(category, course_code, course_name) / "Assignment Submissions"

        out.append({
            "course_id": course_id,
            "course_code": course_code,
            "course_name": course_name,
            "category": category,
            "src": src,
            "dest": dest,
            "assignments": assignment_dirs,
            "loose_files": loose_files,
            "status": "ok",
        })
    return out


def _render_table(mapping: list[dict[str, Any]], submissions_root: Path) -> Table:
    table = Table(title="Submission folder mapping")
    table.add_column("course_code", style="cyan", no_wrap=False, max_width=30)
    table.add_column("category", style="magenta", max_width=20)
    table.add_column("source (rel to submissions root)", max_width=45)
    table.add_column("# items", justify="right")
    table.add_column("status", justify="right")
    for m in mapping:
        if m["status"] == "no source":
            table.add_row(m["course_code"], m["category"], "—", "0", "[yellow]no source[/yellow]")
            continue
        try:
            rel = m["src"].relative_to(submissions_root)
        except ValueError:
            rel = m["src"]
        n_assignments = len(m["assignments"])
        n_loose = len(m["loose_files"])
        items = f"{n_assignments} dirs" + (f" + {n_loose} files" if n_loose else "")
        table.add_row(m["course_code"], m["category"], str(rel), items, "[green]ok[/green]")
    return table


def _copy_one(item: Path, dest_parent: Path) -> tuple[int, int]:
    """Copy `item` (dir or file) into `dest_parent`. Returns (files_copied, errors)."""
    dest_parent.mkdir(parents=True, exist_ok=True)
    dest = dest_parent / item.name
    if item.is_dir():
        shutil.copytree(item, dest, dirs_exist_ok=True)
        # Count files
        n = sum(1 for _ in dest.rglob("*") if _.is_file())
        return n, 0
    else:
        shutil.copy2(item, dest)
        return 1, 0


def run(
    submissions_root: Path | None = None,
    dry_run: bool = False,
) -> int:
    console = Console()
    logger = get_error_logger("canvas_export.submissions")

    sub_root = submissions_root or DEFAULT_SUBMISSIONS_ROOT
    if not sub_root.is_dir():
        console.print(f"[red]Submissions root not found: {sub_root}[/red]")
        return 1

    try:
        rows = read_included_courses()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    console.print(f"[cyan]Scanning submissions root:[/cyan] {sub_root}")
    mapping = _build_mapping(sub_root, rows)

    console.print(_render_table(mapping, sub_root))

    n_ok = sum(1 for m in mapping if m["status"] == "ok")
    n_missing = sum(1 for m in mapping if m["status"] == "no source")
    console.print(
        f"\n[bold]{n_ok}[/bold] courses with submissions to copy, "
        f"[yellow]{n_missing}[/yellow] with no local source folder."
    )

    if dry_run:
        console.print("[yellow]Dry-run only — no files copied.[/yellow]")
        return 0

    # Real copy
    console.print("\n[cyan]Copying submissions…[/cyan]")
    total_files = 0
    total_errors = 0
    for m in mapping:
        if m["status"] != "ok":
            continue
        course_id = m["course_id"]
        dest = m["dest"]
        items = m["assignments"] + m["loose_files"]
        if not items:
            continue

        copied_files = 0
        manifest = load_manifest(course_id)
        manifest["course_id"] = course_id
        manifest["course_code"] = m["course_code"]
        manifest["course_name"] = m["course_name"]
        manifest["category"] = m["category"]
        manifest.setdefault("submissions", [])
        existing_names = {s.get("name") for s in manifest["submissions"]}

        for item in items:
            try:
                n, _ = _copy_one(item, dest)
                copied_files += n
                if item.name not in existing_names:
                    manifest["submissions"].append({
                        "name": item.name,
                        "source_path": str(item),
                        "dest_path": str(dest / item.name),
                        "is_dir": item.is_dir(),
                        "copied_at": now_iso(),
                    })
                    existing_names.add(item.name)
            except Exception as exc:
                logger.error(
                    f"{m['course_code']}: copy '{item.name}' failed: {exc}"
                )
                total_errors += 1
        save_manifest(course_id, manifest)
        console.print(
            f"  [green]{m['course_code']}[/green]: {copied_files} files → "
            f"{dest.relative_to(DOWNLOADS_DIR)}"
        )
        total_files += copied_files

    console.print(
        f"\n[bold]Done.[/bold]  [green]{total_files} files copied[/green]  "
        f"[yellow]{total_errors} errors[/yellow]"
    )
    return 0 if total_errors == 0 else 2
