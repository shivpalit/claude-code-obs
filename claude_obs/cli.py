import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

from .core import (
    aggregate_stats,
    current_project_slug,
    find_sessions,
    get_session,
    list_projects,
    list_sessions,
)


def _fmt_table(rows: list[dict], cols: list[str]) -> str:
    widths = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(row.get(c, "") or "")))
    header = "  ".join(c.ljust(widths[c]) for c in cols)
    sep = "  ".join("-" * widths[c] for c in cols)
    lines = [header, sep]
    for row in rows:
        lines.append("  ".join(str(row.get(c, "") or "").ljust(widths[c]) for c in cols))
    return "\n".join(lines)


def _output(data, fmt: str, cols: list[str] | None = None):
    if fmt == "json":
        print(json.dumps(data, indent=2))
    else:
        if isinstance(data, list) and cols:
            print(_fmt_table(data, cols))
        else:
            print(json.dumps(data, indent=2))


def _add_output(p):
    p.add_argument("--output", choices=["json", "table"], default="json", help="Output format (default: json)")


def main():
    if "--webapp" in sys.argv:
        webapp_path = Path(__file__).parent / "webapp.py"
        subprocess.run([sys.executable, "-m", "streamlit", "run", str(webapp_path)])
        return

    parser = argparse.ArgumentParser(
        prog="claude-obs",
        description="Claude Code session observability — inspect token usage, costs, and tool patterns",
    )
    parser.add_argument("--webapp", action="store_true", help="Launch Streamlit dashboard")
    sub = parser.add_subparsers(dest="command", required=True)

    proj_p = sub.add_parser("projects", help="List all Claude Code projects with session counts and last activity")
    _add_output(proj_p)

    sess = sub.add_parser("sessions", help="List sessions for a project")
    sess.add_argument("--project", default=None, help="Project slug (use --project=<slug> if slug starts with -)")
    sess.add_argument("--sort", choices=["created", "last_message"], default="last_message", help="Sort order (default: last_message)")
    sess.add_argument("--limit", type=int, default=None, help="Maximum number of sessions to return")
    _add_output(sess)

    detail = sub.add_parser("session", help="Full detail for a single session")
    detail.add_argument("session_id", nargs="?", default=None, help="Session UUID")
    detail.add_argument("--latest", action="store_true", help="Use the most recently active session")
    detail.add_argument("--project", default=None, help="Project slug")
    _add_output(detail)

    stats_p = sub.add_parser("stats", help="Aggregate token, cost, and tool stats across all sessions in a project")
    stats_p.add_argument("--project", default=None, help="Project slug")
    _add_output(stats_p)

    search_p = sub.add_parser("search", help="Search sessions by title or opening message")
    search_p.add_argument("query", help="Search term (case-insensitive substring match)")
    search_p.add_argument("--project", default=None, help="Project slug")
    _add_output(search_p)

    sub.add_parser("install-skill", help="Install the claude-obs skill to ~/.claude/skills/claude-obs/")

    args = parser.parse_args()
    slug = getattr(args, "project", None) or current_project_slug()
    fmt = getattr(args, "output", "json")

    if args.command == "projects":
        data = list_projects()
        _output(data, fmt, cols=["slug", "session_count", "last_active"])

    elif args.command == "sessions":
        data = list_sessions(slug, sort=args.sort)
        if args.limit:
            data = data[:args.limit]
        _output(data, fmt, cols=["session_id", "title", "started_at", "duration_mins", "tool_calls", "estimated_cost_usd"])

    elif args.command == "session":
        if args.latest:
            sessions = list_sessions(slug)
            session_id = sessions[0]["session_id"]
        elif args.session_id:
            session_id = args.session_id
        else:
            parser.error("session requires a session_id or --latest")
        _output(get_session(slug, session_id), fmt)

    elif args.command == "stats":
        _output(aggregate_stats(slug), fmt)

    elif args.command == "search":
        data = find_sessions(slug, args.query)
        _output(data, fmt, cols=["session_id", "title", "started_at", "estimated_cost_usd"])

    elif args.command == "install-skill":
        src = Path(__file__).parent / "skills" / "SKILL.md"
        dest_dir = Path.home() / ".claude" / "skills" / "claude-obs"
        dest_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, dest_dir / "SKILL.md")
        print(f"Skill installed to {dest_dir / 'SKILL.md'}")


if __name__ == "__main__":
    main()
