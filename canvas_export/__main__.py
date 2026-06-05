from __future__ import annotations

import argparse
import sys


def _not_implemented(phase: str) -> int:
    print(f"[{phase}] not yet implemented — scaffold only", file=sys.stderr)
    return 1


def _cmd_verify() -> int:
    from rich.console import Console
    from rich.table import Table

    from . import canvas_client

    console = Console()
    try:
        user = canvas_client.verify_token()
    except Exception as exc:
        console.print(f"[red]Token verification failed:[/red] {exc}")
        return 1

    table = Table(title="Canvas user (/users/self)", show_header=False)
    table.add_column("field", style="cyan")
    table.add_column("value")
    for k, v in user.items():
        table.add_row(k, str(v))
    console.print(table)
    console.print("[green]Token works.[/green]")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="canvas_export",
        description="Archive Stanford GSB Canvas course materials to Google Drive.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("verify", help="Hit /users/self to confirm the Canvas token works")
    sub.add_parser("discover", help="Phase 1: list courses, write course_inventory.csv")
    sub.add_parser("categorize",
                   help="Interactively set categories / exclusions in the terminal (no CSV editing)")

    p_subm = sub.add_parser("submissions",
                            help="Copy local submission exports into course folders")
    p_subm.add_argument("--source", type=str, default=None,
                        help="Path to submissions root (defaults to "
                             "..\\2026-06-03 data export submissions)")
    p_subm.add_argument("--dry-run", action="store_true",
                        help="Show mapping only, no files copied")

    p_files = sub.add_parser("files", help="Phase 2: download course files")
    p_files.add_argument("--course-id", type=int, default=None)
    p_files.add_argument("--category", type=str, default=None,
                         help="Only process courses with this category (case-insensitive)")
    p_files.add_argument("--dry-run", action="store_true")

    p_assignments = sub.add_parser("assignments", help="Phase 3a: archive assignments")
    p_assignments.add_argument("--course-id", type=int, default=None)
    p_assignments.add_argument("--category", type=str, default=None,
                               help="Only process courses with this category")
    p_assignments.add_argument("--force", action="store_true",
                               help="Re-render assignments even if already in manifest")
    p_assignments.add_argument("--dry-run", action="store_true")

    p_discussions = sub.add_parser("discussions", help="Phase 3b: archive discussions")
    p_discussions.add_argument("--course-id", type=int, default=None)

    p_recordings = sub.add_parser("recordings", help="Phase 4: detect recordings")
    p_recordings.add_argument("--course-id", type=int, default=None)
    p_recordings.add_argument("--category", type=str, default=None,
                              help="Only scan courses with this category")

    p_upload = sub.add_parser("upload", help="Phase 5: upload to Google Drive")
    p_upload.add_argument("--course-id", type=int, default=None)
    p_upload.add_argument("--dry-run", action="store_true")

    sub.add_parser("all", help="Run phases 2-5 (discover excluded)")
    sub.add_parser("status", help="Progress summary across manifests")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "verify":
        return _cmd_verify()
    if args.command == "discover":
        from . import discover
        return discover.run()
    if args.command == "categorize":
        from . import discover
        return discover.categorize()
    if args.command == "files":
        from . import files
        return files.run(
            course_id=args.course_id,
            category=args.category,
            dry_run=args.dry_run,
        )
    if args.command == "submissions":
        from pathlib import Path
        from . import submissions
        src = Path(args.source) if args.source else None
        return submissions.run(submissions_root=src, dry_run=args.dry_run)
    if args.command == "assignments":
        from . import assignments
        return assignments.run(
            course_id=args.course_id,
            category=args.category,
            force=args.force,
            dry_run=args.dry_run,
        )
    if args.command == "recordings":
        from . import recordings
        return recordings.run(course_id=args.course_id, category=args.category)
    return _not_implemented(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
