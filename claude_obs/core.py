#!/usr/bin/env python3
"""
Claude Code observability API.

Usage:
  python claude_obs.py projects               # List all projects
  python claude_obs.py sessions               # List sessions for current project (cwd)
  python claude_obs.py sessions --project=-home-claude-working
  python claude_obs.py session <session_id>   # Full detail for one session
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

CLAUDE_DIR = Path("/root/.claude")
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Approximate cost per 1M tokens (claude-sonnet-4-6)
COST_PER_1M = {
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_creation": 3.75,
}


def slug_to_path(slug: str) -> str:
    return slug.replace("-", "/", 1) if slug.startswith("-") else "/" + slug.replace("-", "/")


def current_project_slug() -> str:
    return os.getcwd().replace("/", "-")


def parse_ts(ts: str) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        return None


def list_projects() -> list[dict]:
    projects = []
    for entry in sorted(PROJECTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        sessions = list(entry.glob("*.jsonl"))
        latest_mtime = max((s.stat().st_mtime for s in sessions), default=0)
        projects.append({
            "slug": entry.name,
            "path": slug_to_path(entry.name),
            "session_count": len(sessions),
            "last_active": datetime.fromtimestamp(latest_mtime).isoformat() if latest_mtime else None,
        })
    return sorted(projects, key=lambda p: p["last_active"] or "", reverse=True)


def list_sessions(project_slug: str, sort: str = "last_message") -> list[dict]:
    project_dir = PROJECTS_DIR / project_slug
    if not project_dir.exists():
        raise ValueError(f"Project not found: {project_slug}")

    sessions = []
    for f in project_dir.glob("*.jsonl"):
        stat = f.stat()
        summary = _read_session_summary(f)
        sessions.append({
            "session_id": f.stem,
            "file_size_kb": round(stat.st_size / 1024, 1),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            **summary,
        })

    sort_key = "last_modified" if sort == "last_message" else "started_at"
    return sorted(sessions, key=lambda s: s.get(sort_key) or "", reverse=True)


def _read_session_summary(path: Path) -> dict:
    user_count = 0
    assistant_count = 0
    tool_calls = 0
    tool_counts = defaultdict(int)
    first_user_message = None
    title = None
    mode = None
    permission_mode = None
    entrypoint = None
    model = None
    input_tokens = 0
    output_tokens = 0
    cache_read_tokens = 0
    cache_creation_tokens = 0
    started_at = None
    last_ts = None
    git_branch = None

    try:
        with open(path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                t = obj.get("type")
                ts = obj.get("timestamp")
                if ts:
                    if started_at is None:
                        started_at = ts
                    last_ts = ts

                if t == "mode":
                    mode = obj.get("mode")
                elif t == "permission-mode":
                    permission_mode = obj.get("permissionMode")
                elif t == "ai-title":
                    title = obj.get("aiTitle")
                elif t == "user" and not obj.get("isSidechain"):
                    user_count += 1
                    if entrypoint is None:
                        entrypoint = obj.get("entrypoint")
                    if git_branch is None:
                        git_branch = obj.get("gitBranch")
                    if not first_user_message:
                        content = obj.get("message", {}).get("content", "")
                        if isinstance(content, list):
                            text = " ".join(
                                c.get("text", "") for c in content
                                if isinstance(c, dict) and c.get("type") == "text"
                            )
                        else:
                            text = str(content)
                        text = text.strip()
                        first_user_message = text[:80] + ("…" if len(text) > 80 else "")
                elif t == "assistant" and not obj.get("isSidechain"):
                    assistant_count += 1
                    msg = obj.get("message", {})
                    if model is None:
                        model = msg.get("model")
                    usage = msg.get("usage", {})
                    input_tokens += usage.get("input_tokens", 0) or 0
                    output_tokens += usage.get("output_tokens", 0) or 0
                    cache_read_tokens += usage.get("cache_read_input_tokens", 0) or 0
                    cache_creation_tokens += usage.get("cache_creation_input_tokens", 0) or 0
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_calls += 1
                            tool_counts[block["name"]] += 1
    except Exception:
        pass

    # Duration
    duration_mins = None
    if started_at and last_ts:
        t0, t1 = parse_ts(started_at), parse_ts(last_ts)
        if t0 and t1:
            duration_mins = round((t1 - t0).total_seconds() / 60, 1)

    # Estimated cost
    estimated_cost_usd = round(
        input_tokens / 1e6 * COST_PER_1M["input"]
        + output_tokens / 1e6 * COST_PER_1M["output"]
        + cache_read_tokens / 1e6 * COST_PER_1M["cache_read"]
        + cache_creation_tokens / 1e6 * COST_PER_1M["cache_creation"],
        4,
    )

    return {
        "title": title,
        "started_at": started_at,
        "duration_mins": duration_mins,
        "entrypoint": entrypoint,
        "mode": mode,
        "permission_mode": permission_mode,
        "model": model,
        "git_branch": git_branch,
        "first_user_message": first_user_message,
        "user_messages": user_count,
        "assistant_messages": assistant_count,
        "tool_calls": tool_calls,
        "tools_used": dict(sorted(tool_counts.items(), key=lambda x: -x[1])),
        "tokens": {
            "input": input_tokens,
            "output": output_tokens,
            "cache_read": cache_read_tokens,
            "cache_creation": cache_creation_tokens,
        },
        "estimated_cost_usd": estimated_cost_usd,
    }


def get_session(project_slug: str, session_id: str) -> dict:
    path = PROJECTS_DIR / project_slug / f"{session_id}.jsonl"
    if not path.exists():
        raise ValueError(f"Session not found: {session_id}")
    stat = path.stat()
    return {
        "session_id": session_id,
        "file_size_kb": round(stat.st_size / 1024, 1),
        **_read_session_summary(path),
    }


def main():
    parser = argparse.ArgumentParser(description="Claude Code observability")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("projects", help="List all projects")

    sess = sub.add_parser("sessions", help="List sessions for a project")
    sess.add_argument("--project", default=None, help="Project slug (use --project=<slug> if slug starts with -)")
    sess.add_argument("--limit", type=int, default=None, help="Max number of sessions to return")
    sess.add_argument("--sort", choices=["created", "last_message"], default="last_message", help="Sort by session start or last activity")

    detail = sub.add_parser("session", help="Full detail for one session")
    detail.add_argument("session_id", nargs="?", default=None)
    detail.add_argument("--latest", action="store_true", help="Use the most recent session")
    detail.add_argument("--project", default=None)

    args = parser.parse_args()
    slug = getattr(args, "project", None) or current_project_slug()

    if args.command == "projects":
        print(json.dumps(list_projects(), indent=2))
    elif args.command == "sessions":
        sessions = list_sessions(slug, sort=args.sort)
        if args.limit:
            sessions = sessions[:args.limit]
        print(json.dumps(sessions, indent=2))
    elif args.command == "session":
        if args.latest:
            sessions = list_sessions(slug, sort="last_message")
            session_id = sessions[0]["session_id"]
        elif args.session_id:
            session_id = args.session_id
        else:
            parser.error("session requires a session_id or --latest")
        print(json.dumps(get_session(slug, session_id), indent=2))


if __name__ == "__main__":
    main()
