import argparse
import json
import textwrap

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


def main():
    parser = argparse.ArgumentParser(prog="claude-obs", description="Claude Code session observability")
    parser.add_argument("--output", choices=["json", "table"], default="json", help="Output format")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("projects", help="List all projects")

    sess = sub.add_parser("sessions", help="List sessions for a project")
    sess.add_argument("--project", default=None)
    sess.add_argument("--sort", choices=["created", "last_message"], default="last_message")
    sess.add_argument("--limit", type=int, default=None)

    detail = sub.add_parser("session", help="Detail for one session")
    detail.add_argument("session_id", nargs="?", default=None)
    detail.add_argument("--latest", action="store_true")
    detail.add_argument("--project", default=None)

    stats_p = sub.add_parser("stats", help="Aggregate stats for a project")
    stats_p.add_argument("--project", default=None)

    search_p = sub.add_parser("search", help="Search sessions by title or first message")
    search_p.add_argument("query")
    search_p.add_argument("--project", default=None)

    args = parser.parse_args()
    slug = getattr(args, "project", None) or current_project_slug()
    fmt = args.output

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


if __name__ == "__main__":
    main()
