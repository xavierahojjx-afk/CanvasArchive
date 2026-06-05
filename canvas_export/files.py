from __future__ import annotations

import logging
import os
import re
from html import escape as html_escape
from pathlib import Path
from typing import Any

from rich.console import Console
from tqdm import tqdm

from .canvas_client import canvas_retry, get_canvas
from .config import DOWNLOADS_DIR, LOGS_DIR
from .discover import read_included_courses
from .manifest import load_manifest, now_iso, save_manifest
from .utils import get_error_logger, sanitize_filename, sha256_file

_FILE_ID_PATTERNS = [
    re.compile(r'data-api-endpoint="[^"]*?/files/(\d+)\b'),
    re.compile(r'href="[^"]*?/files/(\d+)(?:/download)?(?:\?|#|")'),
    re.compile(r'src="[^"]*?/files/(\d+)(?:/(?:preview|download))?(?:\?|#|")'),
    re.compile(r'data-instructure-file="[^"]*?/files/(\d+)\b'),
]


def _extract_file_ids(html: str) -> list[int]:
    if not html:
        return []
    seen: set[int] = set()
    ordered: list[int] = []
    for pat in _FILE_ID_PATTERNS:
        for m in pat.findall(html):
            try:
                fid = int(m)
            except (TypeError, ValueError):
                continue
            if fid not in seen:
                seen.add(fid)
                ordered.append(fid)
    return ordered


def _course_folder(category: str, course_code: str, course_name: str) -> Path:
    cat = sanitize_filename(category or "Uncategorized", max_length=100)
    folder = sanitize_filename(f"{course_code} - {course_name}", max_length=180)
    return DOWNLOADS_DIR / cat / folder


def _module_folder(course_dir: Path, module_position: int, module_name: str) -> Path:
    pos = f"{module_position:02d}" if module_position else "00"
    name = sanitize_filename(module_name, max_length=100)
    return course_dir / f"{pos} - {name}"


@canvas_retry
def _get_course(canvas, course_id: int):
    return canvas.get_course(course_id, include=["syllabus_body"])


@canvas_retry
def _list_modules(course):
    return list(course.get_modules(per_page=100))


@canvas_retry
def _list_module_items(module):
    return list(module.get_module_items(per_page=100))


@canvas_retry
def _get_file(canvas, file_id: int):
    return canvas.get_file(file_id)


@canvas_retry
def _list_course_files(course):
    return list(course.get_files(per_page=100))


@canvas_retry
def _get_page(course, page_url: str):
    return course.get_page(page_url)


@canvas_retry
def _get_front_page(course):
    return course.show_front_page()


def _save_page_html(module_dir: Path, title: str, body: str) -> Path:
    name = sanitize_filename(title, max_length=180) + ".html"
    dest = module_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{html_escape(title)}</title></head><body>"
        f"<h1>{html_escape(title)}</h1>\n{body or ''}\n"
        "</body></html>\n"
    )
    dest.write_text(doc, encoding="utf-8")
    return dest


def _save_home_page(course_dir: Path, title: str, body: str) -> Path:
    """Save the course's front page (often contains Teaching Team) at course root."""
    safe_title = title or "Home Page"
    name = sanitize_filename(f"_Home - {safe_title}", max_length=180) + ".html"
    dest = course_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{html_escape(safe_title)}</title></head><body>"
        f"<h1>{html_escape(safe_title)}</h1>\n{body or ''}\n"
        "</body></html>\n"
    )
    dest.write_text(doc, encoding="utf-8")
    return dest


def _save_syllabus(course_dir: Path, course_name: str, body: str) -> Path:
    """Save the course syllabus_body (often the actual 'home' when default_view=syllabus)."""
    title = f"Syllabus — {course_name}" if course_name else "Syllabus"
    name = sanitize_filename("_Syllabus", max_length=180) + ".html"
    dest = course_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    doc = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        f"<title>{html_escape(title)}</title></head><body>"
        f"<h1>{html_escape(title)}</h1>\n{body or ''}\n"
        "</body></html>\n"
    )
    dest.write_text(doc, encoding="utf-8")
    return dest


def _record_page(
    manifest: dict[str, Any],
    course_id: int,
    *,
    page_url: str,
    title: str,
    module_name: str,
    local_path: Path,
) -> None:
    entry = {
        "page_url": page_url,
        "title": title,
        "module_name": module_name,
        "local_path": str(local_path),
        "downloaded_at": now_iso(),
    }
    manifest["pages"] = [
        p for p in manifest["pages"]
        if not (p.get("page_url") == page_url and p.get("module_name") == module_name)
    ]
    manifest["pages"].append(entry)
    save_manifest(course_id, manifest)


def _save_external_url(module_dir: Path, title: str, url: str) -> Path:
    """Write a Windows .url shortcut file. Double-click opens in default browser."""
    name = sanitize_filename(title, max_length=180) + ".url"
    dest = module_dir / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(f"[InternetShortcut]\nURL={url}\n", encoding="utf-8")
    return dest


def _record_link(
    manifest: dict[str, Any],
    course_id: int,
    *,
    title: str,
    url: str,
    module_name: str,
    local_path: Path,
) -> None:
    entry = {
        "title": title,
        "url": url,
        "module_name": module_name,
        "local_path": str(local_path),
        "captured_at": now_iso(),
    }
    manifest["links"] = [
        l for l in manifest["links"]
        if not (l.get("url") == url and l.get("module_name") == module_name)
    ]
    manifest["links"].append(entry)
    save_manifest(course_id, manifest)


@canvas_retry
def _download_to(file_obj, dest_path: Path) -> None:
    """Stream download via canvasapi to a .tmp then atomic-rename."""
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


def _record_file(
    manifest: dict[str, Any],
    course_id: int,
    *,
    file_id: int,
    filename: str,
    module_name: str,
    local_path: Path,
    canvas_url: str,
) -> None:
    entry = {
        "file_id": file_id,
        "filename": filename,
        "module_name": module_name,
        "local_path": str(local_path),
        "canvas_url": canvas_url,
        "sha256": sha256_file(local_path),
        "downloaded_at": now_iso(),
        "drive_file_id": None,
    }
    manifest["files"] = [f for f in manifest["files"] if f.get("file_id") != file_id]
    manifest["files"].append(entry)
    save_manifest(course_id, manifest)


def _already_downloaded(manifest: dict[str, Any], file_id: int) -> bool:
    entry = next((f for f in manifest["files"] if f.get("file_id") == file_id), None)
    return bool(entry and Path(entry.get("local_path", "")).exists())


def _archive_course(
    row: dict[str, str],
    canvas,
    logger: logging.Logger,
    console: Console,
) -> tuple[int, int, int]:
    course_id = int(row["course_id"])
    course_code = row["course_code"]
    course_name = row["name"]
    category = row.get("category", "")

    console.print(f"\n[cyan]== {course_code}[/cyan]  [dim]{course_name}[/dim]")
    course_dir = _course_folder(category, course_code, course_name)

    manifest = load_manifest(course_id)
    manifest["course_id"] = course_id
    manifest["course_code"] = course_code
    manifest["course_name"] = course_name
    manifest["category"] = category

    downloaded = skipped = errored = 0

    try:
        course = _get_course(canvas, course_id)
        modules = _list_modules(course)
    except Exception as exc:
        logger.error(f"{course_code} ({course_id}): list modules failed: {exc}")
        console.print(f"  [red]list modules failed: {exc}[/red]")
        return 0, 0, 1

    seen_file_ids: set[int] = set()

    # Syllabus body — at GSB this is where Teaching Team lives when default_view=syllabus
    syllabus_body = getattr(course, "syllabus_body", "") or ""
    if syllabus_body:
        try:
            syl_path = _save_syllabus(course_dir, course_name, syllabus_body)
            manifest["syllabus"] = {
                "local_path": str(syl_path),
                "char_count": len(syllabus_body),
                "downloaded_at": now_iso(),
            }
            save_manifest(course_id, manifest)

            for file_id in _extract_file_ids(syllabus_body):
                if file_id in seen_file_ids:
                    continue
                seen_file_ids.add(file_id)
                if _already_downloaded(manifest, file_id):
                    skipped += 1
                    continue
                try:
                    f = _get_file(canvas, file_id)
                    filename = sanitize_filename(
                        getattr(f, "display_name", "")
                        or getattr(f, "filename", "")
                        or f"file_{file_id}"
                    )
                    dest = course_dir / filename
                    _download_to(f, dest)
                    _record_file(
                        manifest, course_id,
                        file_id=file_id,
                        filename=filename,
                        module_name="_syllabus",
                        local_path=dest,
                        canvas_url=getattr(f, "url", "") or "",
                    )
                    downloaded += 1
                except Exception as exc:
                    logger.error(
                        f"{course_code}: file {file_id} (from syllabus): "
                        f"download failed: {exc}"
                    )
                    errored += 1
        except Exception as exc:
            logger.error(f"{course_code}: save syllabus failed: {exc}")

    # Home page (front page) — used when default_view=wiki
    try:
        front = _get_front_page(course)
        home_title = getattr(front, "title", "") or "Home Page"
        home_body = getattr(front, "body", "") or ""
        home_path = _save_home_page(course_dir, home_title, home_body)
        manifest["home_page"] = {
            "title": home_title,
            "url": getattr(front, "url", "") or "",
            "local_path": str(home_path),
            "downloaded_at": now_iso(),
        }
        save_manifest(course_id, manifest)

        for file_id in _extract_file_ids(home_body):
            if file_id in seen_file_ids:
                continue
            seen_file_ids.add(file_id)
            if _already_downloaded(manifest, file_id):
                skipped += 1
                continue
            try:
                f = _get_file(canvas, file_id)
                filename = sanitize_filename(
                    getattr(f, "display_name", "")
                    or getattr(f, "filename", "")
                    or f"file_{file_id}"
                )
                dest = course_dir / filename
                _download_to(f, dest)
                _record_file(
                    manifest, course_id,
                    file_id=file_id,
                    filename=filename,
                    module_name="_home_page",
                    local_path=dest,
                    canvas_url=getattr(f, "url", "") or "",
                )
                downloaded += 1
            except Exception as exc:
                logger.error(
                    f"{course_code}: file {file_id} (from home page): "
                    f"download failed: {exc}"
                )
                errored += 1
    except Exception as exc:
        msg = str(exc).lower()
        if "404" in msg or "not found" in msg or "no front page" in msg:
            pass  # course has no front page set — that's fine, common
        else:
            logger.error(f"{course_code}: home page fetch failed: {exc}")

    for module in modules:
        try:
            items = _list_module_items(module)
        except Exception as exc:
            logger.error(
                f"{course_code}: module '{getattr(module, 'name', '?')}': list items failed: {exc}"
            )
            errored += 1
            continue

        relevant = [
            it for it in items
            if getattr(it, "type", "") in ("File", "Page", "ExternalUrl")
        ]
        if not relevant:
            continue

        module_pos = getattr(module, "position", 0) or 0
        module_name = getattr(module, "name", "Unnamed module") or "Unnamed module"
        module_dir = _module_folder(course_dir, module_pos, module_name)

        bar = tqdm(relevant, desc=f"  {module_name[:40]}", leave=False, unit="item")
        for item in bar:
            item_type = getattr(item, "type", "")

            if item_type == "File":
                file_id = getattr(item, "content_id", None)
                if not file_id:
                    continue
                seen_file_ids.add(file_id)
                if _already_downloaded(manifest, file_id):
                    skipped += 1
                    continue
                try:
                    f = _get_file(canvas, file_id)
                    filename = sanitize_filename(
                        getattr(f, "display_name", "")
                        or getattr(f, "filename", "")
                        or f"file_{file_id}"
                    )
                    dest = module_dir / filename
                    _download_to(f, dest)
                    _record_file(
                        manifest, course_id,
                        file_id=file_id,
                        filename=filename,
                        module_name=module_name,
                        local_path=dest,
                        canvas_url=getattr(f, "url", "") or "",
                    )
                    downloaded += 1
                except Exception as exc:
                    logger.error(f"{course_code}: file {file_id}: download failed: {exc}")
                    errored += 1

            elif item_type == "ExternalUrl":
                url = getattr(item, "external_url", "") or ""
                title = getattr(item, "title", "") or "link"
                if not url:
                    continue
                try:
                    local_url = _save_external_url(module_dir, title, url)
                    _record_link(
                        manifest, course_id,
                        title=title, url=url,
                        module_name=module_name, local_path=local_url,
                    )
                except Exception as exc:
                    logger.error(
                        f"{course_code}: external url '{title}': save failed: {exc}"
                    )
                    errored += 1

            elif item_type == "Page":
                page_url = getattr(item, "page_url", None)
                page_title = getattr(item, "title", "") or page_url or "page"
                if not page_url:
                    continue
                try:
                    page = _get_page(course, page_url)
                    title = getattr(page, "title", "") or page_title
                    body = getattr(page, "body", "") or ""
                except Exception as exc:
                    logger.error(
                        f"{course_code}: page '{page_title}': fetch failed: {exc}"
                    )
                    errored += 1
                    continue

                try:
                    local_html = _save_page_html(module_dir, title, body)
                    _record_page(
                        manifest, course_id,
                        page_url=page_url,
                        title=title,
                        module_name=module_name,
                        local_path=local_html,
                    )
                except Exception as exc:
                    logger.error(
                        f"{course_code}: page '{title}': save html failed: {exc}"
                    )
                    errored += 1

                for file_id in _extract_file_ids(body):
                    if file_id in seen_file_ids:
                        continue
                    seen_file_ids.add(file_id)
                    if _already_downloaded(manifest, file_id):
                        skipped += 1
                        continue
                    try:
                        f = _get_file(canvas, file_id)
                        filename = sanitize_filename(
                            getattr(f, "display_name", "")
                            or getattr(f, "filename", "")
                            or f"file_{file_id}"
                        )
                        dest = module_dir / filename
                        _download_to(f, dest)
                        _record_file(
                            manifest, course_id,
                            file_id=file_id,
                            filename=filename,
                            module_name=module_name,
                            local_path=dest,
                            canvas_url=getattr(f, "url", "") or "",
                        )
                        downloaded += 1
                    except Exception as exc:
                        logger.error(
                            f"{course_code}: file {file_id} (from page '{title}'): "
                            f"download failed: {exc}"
                        )
                        errored += 1
        bar.close()

    # Unlinked files: anything in /files not already grabbed via modules
    try:
        all_files = _list_course_files(course)
    except Exception as exc:
        logger.error(f"{course_code}: list /files failed: {exc}")
        all_files = []

    unlinked = [f for f in all_files if getattr(f, "id", None) and f.id not in seen_file_ids]
    if unlinked:
        bar = tqdm(unlinked, desc="  _unlinked_files", leave=False, unit="file")
        for f in bar:
            file_id = f.id
            if _already_downloaded(manifest, file_id):
                skipped += 1
                continue
            try:
                filename = sanitize_filename(
                    getattr(f, "display_name", "")
                    or getattr(f, "filename", "")
                    or f"file_{file_id}"
                )
                dest = course_dir / "_unlinked_files" / filename
                _download_to(f, dest)
                _record_file(
                    manifest, course_id,
                    file_id=file_id,
                    filename=filename,
                    module_name="_unlinked_files",
                    local_path=dest,
                    canvas_url=getattr(f, "url", "") or "",
                )
                downloaded += 1
            except Exception as exc:
                logger.error(f"{course_code}: unlinked file {file_id}: download failed: {exc}")
                errored += 1
        bar.close()

    pages_count = len(manifest.get("pages", []))
    links_count = len(manifest.get("links", []))
    console.print(
        f"  [green]{downloaded} files downloaded[/green]  "
        f"[blue]{pages_count} pages saved[/blue]  "
        f"[magenta]{links_count} links saved[/magenta]  "
        f"[dim]{skipped} skipped[/dim]  "
        f"[yellow]{errored} errors[/yellow]"
    )
    return downloaded, skipped, errored


def run(
    course_id: int | None = None,
    category: str | None = None,
    dry_run: bool = False,
) -> int:
    console = Console()
    logger = get_error_logger("canvas_export.files")
    canvas = get_canvas()

    try:
        rows = read_included_courses()
    except FileNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        return 1

    if course_id is not None:
        rows = [r for r in rows if str(r["course_id"]) == str(course_id)]
        if not rows:
            console.print(
                f"[red]Course {course_id} not in inventory (or include=FALSE)[/red]"
            )
            return 1

    if category is not None:
        cat_lower = category.strip().lower()
        rows = [r for r in rows if r.get("category", "").strip().lower() == cat_lower]
        if not rows:
            console.print(
                f"[red]No included courses found with category '{category}'[/red]"
            )
            return 1

    if dry_run:
        console.print(f"[yellow]Dry run — would process {len(rows)} course(s):[/yellow]")
        for r in rows:
            console.print(
                f"  {r['course_code']} → {r.get('category') or '(uncategorized)'}/"
            )
        return 0

    console.print(
        f"[cyan]Phase 2: archiving files for {len(rows)} course(s)…[/cyan]"
    )
    total_d = total_s = total_e = 0
    for row in rows:
        d, s, e = _archive_course(row, canvas, logger, console)
        total_d += d
        total_s += s
        total_e += e

    console.print(
        f"\n[bold]Done.[/bold]  [green]{total_d} downloaded[/green]  "
        f"[dim]{total_s} skipped[/dim]  [yellow]{total_e} errors[/yellow]"
    )
    if total_e:
        console.print(f"See [bold]{LOGS_DIR / 'errors.log'}[/bold] for details.")
    return 0 if total_e == 0 else 2
