import argparse
import json
import shutil
import subprocess
import sys
import textwrap
from datetime import datetime, timezone
from importlib.metadata import version as pkg_version
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


def _generate_skill_md(python_path: str) -> str:
    cmd = str(Path(python_path).parent / "claude-obs")
    return f"""# claude-obs

Claude Code session observability — inspect token usage, costs, tool patterns, and session history.

**CLI:** `{cmd}`

## Commands

**List projects**
```
{cmd} projects
{cmd} projects --output table
```

**List sessions**
```
{cmd} sessions --project=-home-myproject --output table --limit 10
{cmd} sessions --project=-home-myproject --sort created
```

**Session detail**
```
{cmd} session --latest --project=-home-myproject
{cmd} session <session-uuid> --project=-home-myproject
```

**Aggregate stats**
```
{cmd} stats --project=-home-myproject
```

**Search sessions**
```
{cmd} search "keyword" --project=-home-myproject
```

## Finding your project slug

Run `{cmd} projects` to list all slugs. Use `--project=<slug>` (with `=`) when the slug starts with `-`.

## Cost estimates

Estimated using live Anthropic pricing (falls back to hardcoded rates). Useful as a relative measure — not actual billing.
"""


def _install_skill():
    try:
        current_version = pkg_version("claude-code-obs")
    except Exception:
        current_version = "unknown"

    python_path = sys.executable

    # --- Ask global or project ---
    cwd = Path.cwd()
    project_claude_dir = cwd / ".claude"
    has_project = project_claude_dir.exists()

    if has_project:
        print(f"Claude project detected: {cwd}")
        print("  [1] Global  (~/.claude/skills/claude-obs/)  [default]")
        print(f"  [2] Project ({cwd}/.claude/skills/claude-obs/)")
        choice = input("Choice [1/2, Enter=global]: ").strip()
    else:
        print("No .claude/ folder found in current directory — installing globally.")
        choice = "1"

    if choice == "2":
        dest_dir = project_claude_dir / "skills" / "claude-obs"
    else:
        dest_dir = Path.home() / ".claude" / "skills" / "claude-obs"

    print(f"\nTarget: {dest_dir}")

    # --- Check existing install ---
    paths_file = dest_dir / "paths.json"
    if paths_file.exists():
        try:
            existing = json.loads(paths_file.read_text())
            print("\nExisting install found:")
            print(f"  version : {existing.get('version', 'unknown')}")
            print(f"  python  : {existing.get('python', 'unknown')}")
            if existing.get("version") != current_version:
                print(f"  ⚠ Version mismatch (installed: {existing.get('version')}, current: {current_version})")
            if existing.get("python") != python_path:
                print(f"  ⚠ Python path differs — skill will point to a different environment")
            overwrite = input("\nOverwrite? [y/N]: ").strip().lower()
            if overwrite != "y":
                print("Aborted.")
                return
        except Exception:
            pass

    # --- Write ---
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths_data = {
        "version": current_version,
        "python": python_path,
        "installed_at": datetime.now(timezone.utc).isoformat(),
    }
    paths_file.write_text(json.dumps(paths_data, indent=2))
    (dest_dir / "SKILL.md").write_text(_generate_skill_md(python_path))
    print(f"\nSkill installed to {dest_dir}")
    print(f"  SKILL.md  — uses {python_path}")
    print(f"  paths.json — version {current_version}")


def main():
    if "--webapp" in sys.argv:
        pkg_dir = Path(__file__).parent
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", str(pkg_dir / "webapp.py")],
            cwd=pkg_dir,
        )
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
        _install_skill()


if __name__ == "__main__":
    main()
