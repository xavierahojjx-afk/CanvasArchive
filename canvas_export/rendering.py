from __future__ import annotations

from html import escape
from pathlib import Path
from typing import Any

try:
    from weasyprint import HTML as _WeasyHTML
    WEASYPRINT_OK = True
    _WEASY_ERR: str | None = None
except Exception as _exc:
    _WeasyHTML = None
    WEASYPRINT_OK = False
    _WEASY_ERR = f"{type(_exc).__name__}: {_exc}"


def weasyprint_error() -> str | None:
    return _WEASY_ERR


_BASE_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
       margin: 2em; color: #222; line-height: 1.5; max-width: 50em; }
h1 { border-bottom: 2px solid #444; padding-bottom: 0.3em; }
h2 { color: #555; margin-top: 2em; border-bottom: 1px solid #ddd; padding-bottom: 0.2em; }
.meta { background: #f5f5f5; padding: 1em; border-left: 4px solid #888;
        margin: 1em 0; font-size: 0.95em; }
.meta dt { font-weight: bold; display: inline-block; min-width: 6em; }
.score { color: #1a7f37; font-weight: bold; }
.score.missing { color: #999; font-weight: normal; font-style: italic; }
.comment { background: #fff7e0; padding: 0.8em; border-left: 4px solid #d49a00;
           margin: 0.5em 0; }
.attachments { background: #eef; padding: 0.8em; border-left: 4px solid #4060c0;
               margin: 0.5em 0; }
.attachments ul { margin: 0.3em 0 0.3em 1.2em; padding: 0; }
.note { color: #777; font-size: 0.9em; font-style: italic; }
hr { border: none; border-top: 1px dashed #ccc; margin: 1.5em 0; }
img { max-width: 100%; }
"""


def _attach_list_html(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<em class="note">(none)</em>'
    lis = []
    for a in items:
        name = a.get("display_name") or a.get("filename") or "file"
        lis.append(f"<li>{escape(str(name))}</li>")
    return "<ul>" + "".join(lis) + "</ul>"


def _comments_html(items: list[dict[str, Any]]) -> str:
    if not items:
        return '<em class="note">(no comments)</em>'
    out = []
    for c in items:
        who = c.get("author_name") or c.get("author", {}).get("display_name") or "unknown"
        when = c.get("created_at") or ""
        text = (c.get("comment") or "").replace("\n", "<br>")
        out.append(
            f'<div class="comment"><strong>{escape(str(who))}</strong> '
            f'<em class="note">{escape(str(when))}</em><br>{text}</div>'
        )
    return "".join(out)


def render_assignment_html(
    course_code: str,
    course_name: str,
    assignment: dict[str, Any],
    submission: dict[str, Any],
    assignment_attachments: list[dict[str, Any]],
    submission_attachments: list[dict[str, Any]],
) -> str:
    a_name = assignment.get("name", "Untitled assignment")
    due_at = assignment.get("due_at") or "—"
    points_possible = assignment.get("points_possible")
    score = submission.get("score")

    if score is None:
        score_html = '<span class="score missing">not graded / no submission</span>'
    elif points_possible:
        score_html = f'<span class="score">{score} / {points_possible}</span>'
    else:
        score_html = f'<span class="score">{score}</span>'

    description = assignment.get("description") or '<em class="note">(no description)</em>'
    submission_text = submission.get("body") or ""
    submission_state = submission.get("workflow_state") or "—"
    submitted_at = submission.get("submitted_at") or "—"

    sub_body_html = submission_text if submission_text else '<em class="note">(no typed submission body)</em>'

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>{escape(str(a_name))}</title>
<style>{_BASE_CSS}</style></head>
<body>
<h1>{escape(str(a_name))}</h1>

<div class="meta">
<dt>Course:</dt> {escape(course_code)} — {escape(course_name)}<br>
<dt>Due:</dt> {escape(str(due_at))}<br>
<dt>Submitted:</dt> {escape(str(submitted_at))} <em class="note">({escape(str(submission_state))})</em><br>
<dt>Score:</dt> {score_html}
</div>

<h2>Assignment description</h2>
<div>{description}</div>

<h2>My submission text</h2>
<div>{sub_body_html}</div>

<h2>My submitted files</h2>
<div class="attachments">{_attach_list_html(submission_attachments)}
<p class="note">Submitted files are NOT re-downloaded by this archive tool — see the
<code>Assignment Submissions/</code> folder at the course root for your local copies.</p>
</div>

<h2>Assignment-side attachments (instructor files)</h2>
<div class="attachments">{_attach_list_html(assignment_attachments)}</div>

<h2>Instructor comments</h2>
{_comments_html(submission.get("submission_comments", []))}
</body></html>
"""


def write_pdf_or_html(html_str: str, dest_pdf: Path) -> tuple[Path, str]:
    """Try weasyprint; on any failure, write HTML next to it. Returns (path, kind)."""
    if WEASYPRINT_OK and _WeasyHTML is not None:
        try:
            dest_pdf.parent.mkdir(parents=True, exist_ok=True)
            _WeasyHTML(string=html_str).write_pdf(str(dest_pdf))
            return dest_pdf, "pdf"
        except Exception:
            pass
    dest_html = dest_pdf.with_suffix(".html")
    dest_html.parent.mkdir(parents=True, exist_ok=True)
    dest_html.write_text(html_str, encoding="utf-8")
    return dest_html, "html"
