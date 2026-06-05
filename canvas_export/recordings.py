from __future__ import annotations

import csv
import re
from html import unescape
from pathlib import Path

from rich.console import Console

from .config import RECORDINGS_CSV
from .discover import read_included_courses
from .manifest import load_manifest, now_iso

CANVAS_BASE = "https://canvas.stanford.edu"

_RECORDING_RE = re.compile(
    r'https?://[^\s"\'<>]*(?:'
    r'panopto'
    r'|zoom\.us/rec'
    r'|canvas\.[^/]*studio'
    r'|youtube\.com/watch'
    r'|youtu\.be/'
    r'|vimeo\.com/'
    r'|kaltura'
    r')[^\s"\'<>]*',
    re.IGNORECASE,
)

CSV_HEADERS = [
    "course_code",
    "module_name",
    "item_name",
    "item_type",
    "url",
    "canvas_url",
    "detected_at",
]


def _extract_urls(text: str) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    out: list[str] = []
    for m in _RECORDING_RE.findall(unescape(text)):
        u = m.rstrip(".,);:]")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def _read_file_safely(path_str: str) -> str:
    if not path_str:
        return ""
    p = Path(path_str)
    if not p.exists():
        return ""
    try:
        return p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""


def _load_existing(csv_path: Path) -> set[tuple[str, str]]:
    if not csv_path.exists():
        return set()
    seen: set[tuple[str, str]] = set()
    with csv_path.open("r", newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cc = row.get("course_code", "")
            u = row.get("url", "")
            if cc and u:
                seen.add((cc, u))
    return seen


def _scan_course(
    row: dict[str, str],
    writer: csv.DictWriter,
    seen: set[tuple[str, str]],
) -> int:
    course_id = int(row["course_id"])
    course_code = row["course_code"]
    manifest = load_manifest(course_id)
    added = 0

    def add(url: str, module_name: str, item_name: str, item_type: str, canvas_url: str) -> None:
        nonlocal added
        key = (course_code, url)
        if key in seen:
            return
        seen.add(key)
        writer.writerow({
            "course_code": course_code,
            "module_name": module_name,
            "item_name": item_name,
            "item_type": item_type,
            "url": url,
            "canvas_url": canvas_url,
            "detected_at": now_iso(),
        })
        added += 1

    # ExternalUrl items: the URL itself is the link
    for link in manifest.get("links", []):
        url = link.get("url", "") or ""
        if url and _RECORDING_RE.search(url):
            add(url, link.get("module_name", ""), link.get("title", ""), "ExternalUrl", "")

    # Pages: scan body
    for page in manifest.get("pages", []):
        text = _read_file_safely(page.get("local_path", ""))
        if not text:
            continue
        page_url = page.get("page_url", "")
        cu = f"{CANVAS_BASE}/courses/{course_id}/pages/{page_url}" if page_url else ""
        for url in _extract_urls(text):
            add(url, page.get("module_name", ""), page.get("title", ""), "Page", cu)

    # Home page
    hp = manifest.get("home_page")
    if hp:
        text = _read_file_safely(hp.get("local_path", ""))
        if text:
            for url in _extract_urls(text):
                add(url, "_home_page", hp.get("title", "Home Page"), "HomePage",
                    f"{CANVAS_BASE}/courses/{course_id}")

    # Syllabus
    syl = manifest.get("syllabus")
    if syl:
        text = _read_file_safely(syl.get("local_path", ""))
        if text:
            for url in _extract_urls(text):
                add(url, "_syllabus", "Syllabus", "Syllabus",
                    f"{CANVAS_BASE}/courses/{course_id}/assignments/syllabus")

    # Assignment HTMLs (rendered descriptions + comments)
    for asn in manifest.get("assignments", []):
        text = _read_file_safely(asn.get("render_path", ""))
        if not text:
            continue
        a_id = asn.get("assignment_id", "")
        cu = f"{CANVAS_BASE}/courses/{course_id}/assignments/{a_id}" if a_id else ""
        for url in _extract_urls(text):
            add(url, "_assignment", asn.get("name", ""), "Assignment", cu)

    return added


def run(course_id: int | None = None, category: str | None = None) -> int:
    console = Console()

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

    seen = _load_existing(RECORDINGS_CSV)
    pre_count = len(seen)
    is_new = not RECORDINGS_CSV.exists()

    console.print(
        f"[cyan]Phase 4: scanning {len(rows)} course(s) for recording links…[/cyan]"
    )
    if pre_count:
        console.print(f"[dim]Existing CSV has {pre_count} rows; deduping by (course_code, url).[/dim]")

    total_new = 0
    with RECORDINGS_CSV.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if is_new:
            writer.writeheader()
        for row in rows:
            n = _scan_course(row, writer, seen)
            if n:
                console.print(f"  [cyan]{row['course_code']}[/cyan]: +{n} new")
            total_new += n

    console.print(
        f"\n[bold]Done.[/bold]  [green]{total_new} new recordings[/green]  "
        f"[dim](total now {len(seen)})[/dim]"
    )
    console.print(f"  CSV: [bold]{RECORDINGS_CSV}[/bold]")
    return 0
