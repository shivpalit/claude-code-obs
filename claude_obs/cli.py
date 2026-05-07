import argparse
import json

from .core import (
    aggregate_stats,
    current_project_slug,
    find_sessions,
    get_session,
    list_projects,
    list_sessions,
)


def main():
    parser = argparse.ArgumentParser(prog="claude-obs", description="Claude Code session observability")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("projects", help="List all projects")

    sess = sub.add_parser("sessions", help="List sessions for a project")
    sess.add_argument("--project", default=None)
    sess.add_argument("--sort", choices=["created", "last_message"], default="last_message")

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

    if args.command == "projects":
        print(json.dumps(list_projects(), indent=2))

    elif args.command == "sessions":
        print(json.dumps(list_sessions(slug, sort=args.sort), indent=2))

    elif args.command == "session":
        if args.latest:
            sessions = list_sessions(slug)
            session_id = sessions[0]["session_id"]
        elif args.session_id:
            session_id = args.session_id
        else:
            parser.error("session requires a session_id or --latest")
        print(json.dumps(get_session(slug, session_id), indent=2))

    elif args.command == "stats":
        print(json.dumps(aggregate_stats(slug), indent=2))

    elif args.command == "search":
        print(json.dumps(find_sessions(slug, args.query), indent=2))


if __name__ == "__main__":
    main()
