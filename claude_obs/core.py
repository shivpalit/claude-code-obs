import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CLAUDE_DIR = Path("/root/.claude")
PROJECTS_DIR = CLAUDE_DIR / "projects"

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


def _calc_cost(tokens: dict) -> float:
    return round(
        tokens["input"] / 1e6 * COST_PER_1M["input"]
        + tokens["output"] / 1e6 * COST_PER_1M["output"]
        + tokens["cache_read"] / 1e6 * COST_PER_1M["cache_read"]
        + tokens["cache_creation"] / 1e6 * COST_PER_1M["cache_creation"],
        4,
    )


def _extract_text(content) -> str:
    if isinstance(content, list):
        return " ".join(c.get("text", "") for c in content if isinstance(c, dict) and c.get("type") == "text")
    return str(content)


def _parse_usage(msg: dict) -> dict:
    usage = msg.get("usage", {})
    return {
        "input": usage.get("input_tokens", 0) or 0,
        "output": usage.get("output_tokens", 0) or 0,
        "cache_read": usage.get("cache_read_input_tokens", 0) or 0,
        "cache_creation": usage.get("cache_creation_input_tokens", 0) or 0,
    }


def _read_session_summary(path: Path) -> dict:
    user_count = 0
    assistant_count = 0
    tool_counts = defaultdict(int)
    first_user_message = None
    title = None
    mode = None
    permission_mode = None
    entrypoint = None
    model = None
    tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
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
                        text = _extract_text(obj.get("message", {}).get("content", "")).strip()
                        first_user_message = text[:80] + ("…" if len(text) > 80 else "")
                elif t == "assistant" and not obj.get("isSidechain"):
                    assistant_count += 1
                    msg = obj.get("message", {})
                    if model is None:
                        model = msg.get("model")
                    t_usage = _parse_usage(msg)
                    for k in tokens:
                        tokens[k] += t_usage[k]
                    for block in msg.get("content", []):
                        if isinstance(block, dict) and block.get("type") == "tool_use":
                            tool_counts[block["name"]] += 1
    except Exception:
        pass

    duration_mins = None
    if started_at and last_ts:
        t0, t1 = parse_ts(started_at), parse_ts(last_ts)
        if t0 and t1:
            duration_mins = round((t1 - t0).total_seconds() / 60, 1)

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
        "tool_calls": sum(tool_counts.values()),
        "tools_used": dict(sorted(tool_counts.items(), key=lambda x: -x[1])),
        "tokens": tokens,
        "estimated_cost_usd": _calc_cost(tokens),
    }


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


def get_session_messages(project_slug: str, session_id: str) -> list[dict]:
    path = PROJECTS_DIR / project_slug / f"{session_id}.jsonl"
    if not path.exists():
        raise ValueError(f"Session not found: {session_id}")

    messages = []
    try:
        with open(path) as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                t = obj.get("type")
                if t not in ("user", "assistant") or obj.get("isSidechain"):
                    continue
                msg = obj.get("message", {})
                entry = {
                    "role": t,
                    "timestamp": obj.get("timestamp"),
                    "content": msg.get("content", ""),
                }
                if t == "assistant":
                    entry["model"] = msg.get("model")
                    entry["usage"] = _parse_usage(msg)
                messages.append(entry)
    except Exception:
        pass

    return messages
