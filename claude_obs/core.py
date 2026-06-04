import io
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CLAUDE_DIR = Path("/root/.claude")
PROJECTS_DIR = CLAUDE_DIR / "projects"

# Hardcoded fallback — source: https://platform.claude.com/docs/en/about-claude/pricing
_PRICING_FALLBACK = {
    "claude-opus-4-8":   {"input": 5.00, "cache_write_5m": 6.25,  "cache_write_1h": 10.0, "cache_read": 0.50, "output": 25.0},
    "claude-opus-4-7":   {"input": 5.00, "cache_write_5m": 6.25,  "cache_write_1h": 10.0, "cache_read": 0.50, "output": 25.0},
    "claude-opus-4-6":   {"input": 5.00, "cache_write_5m": 6.25,  "cache_write_1h": 10.0, "cache_read": 0.50, "output": 25.0},
    "claude-opus-4-5":   {"input": 5.00, "cache_write_5m": 6.25,  "cache_write_1h": 10.0, "cache_read": 0.50, "output": 25.0},
    "claude-opus-4-1":   {"input": 15.0, "cache_write_5m": 18.75, "cache_write_1h": 30.0, "cache_read": 1.50, "output": 75.0},
    "claude-opus-4":     {"input": 15.0, "cache_write_5m": 18.75, "cache_write_1h": 30.0, "cache_read": 1.50, "output": 75.0},
    "claude-sonnet-4-6": {"input": 3.00, "cache_write_5m": 3.75,  "cache_write_1h": 6.0,  "cache_read": 0.30, "output": 15.0},
    "claude-sonnet-4-5": {"input": 3.00, "cache_write_5m": 3.75,  "cache_write_1h": 6.0,  "cache_read": 0.30, "output": 15.0},
    "claude-sonnet-4":   {"input": 3.00, "cache_write_5m": 3.75,  "cache_write_1h": 6.0,  "cache_read": 0.30, "output": 15.0},
    "claude-haiku-4-5":  {"input": 1.00, "cache_write_5m": 1.25,  "cache_write_1h": 2.0,  "cache_read": 0.10, "output": 5.0},
    "claude-haiku-3-5":  {"input": 0.80, "cache_write_5m": 1.00,  "cache_write_1h": 1.6,  "cache_read": 0.08, "output": 4.0},
    "_default":          {"input": 3.00, "cache_write_5m": 3.75,  "cache_write_1h": 6.0,  "cache_read": 0.30, "output": 15.0},
}


def _model_name_to_id(name: str) -> str:
    name = name.split("(")[0].strip().lower()
    return name.replace(" ", "-").replace(".", "-")


def _fetch_pricing() -> dict:
    import requests
    from bs4 import BeautifulSoup
    import pandas as pd

    r = requests.get("https://platform.claude.com/docs/en/about-claude/pricing", timeout=5)
    soup = BeautifulSoup(r.text, "html.parser")
    tables = [pd.read_html(io.StringIO(str(t)))[0] for t in soup.find_all("table")]
    df = tables[0]
    df.columns = ["model", "input", "cache_write_5m", "cache_write_1h", "cache_read", "output"]

    pricing = {}
    for _, row in df.iterrows():
        model_id = _model_name_to_id(str(row["model"]))
        def parse_price(val):
            return float(str(val).replace("$", "").replace("/ MTok", "").replace("/MTok", "").strip())
        pricing[model_id] = {
            "input":          parse_price(row["input"]),
            "cache_write_5m": parse_price(row["cache_write_5m"]),
            "cache_write_1h": parse_price(row["cache_write_1h"]),
            "cache_read":     parse_price(row["cache_read"]),
            "output":         parse_price(row["output"]),
        }
    pricing["_default"] = pricing.get("claude-sonnet-4-6", _PRICING_FALLBACK["_default"])
    return pricing


def _load_pricing() -> dict:
    try:
        return _fetch_pricing()
    except Exception:
        return _PRICING_FALLBACK


PRICING = _load_pricing()


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


def _calc_cost(tokens: dict, model: str | None = None) -> float:
    rates = PRICING.get(model or "", PRICING["_default"])
    return round(
        tokens["input"] / 1e6 * rates["input"]
        + tokens["output"] / 1e6 * rates["output"]
        + tokens["cache_read"] / 1e6 * rates["cache_read"]
        + tokens["cache_creation"] / 1e6 * rates["cache_write_5m"],
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
        "estimated_cost_usd": _calc_cost(tokens, model),
    }


def _read_project_cwd(session_files: list[Path]) -> str | None:
    for f in session_files:
        try:
            with open(f) as fh:
                for line in fh:
                    try:
                        obj = json.loads(line)
                        if obj.get("type") == "user" and obj.get("cwd"):
                            return obj["cwd"]
                    except json.JSONDecodeError:
                        continue
        except Exception:
            continue
    return None


def list_projects() -> list[dict]:
    projects = []
    for entry in sorted(PROJECTS_DIR.iterdir()):
        if not entry.is_dir():
            continue
        sessions = list(entry.glob("*.jsonl"))
        latest_mtime = max((s.stat().st_mtime for s in sessions), default=0)
        cwd = _read_project_cwd(sessions)
        projects.append({
            "slug": entry.name,
            "path": cwd or slug_to_path(entry.name),
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


def find_sessions(project_slug: str, query: str) -> list[dict]:
    query = query.lower()
    sessions = list_sessions(project_slug)
    results = []
    for s in sessions:
        title = (s.get("title") or "").lower()
        first = (s.get("first_user_message") or "").lower()
        if query in title or query in first:
            results.append(s)
    return results


def aggregate_stats(project_slug: str) -> dict:
    sessions = list_sessions(project_slug)
    total_tokens = {"input": 0, "output": 0, "cache_read": 0, "cache_creation": 0}
    total_cost = 0.0
    total_tool_calls = 0
    tool_totals = defaultdict(int)
    total_duration = 0.0

    for s in sessions:
        for k in total_tokens:
            total_tokens[k] += s.get("tokens", {}).get(k, 0)
        total_cost += s.get("estimated_cost_usd", 0)
        total_tool_calls += s.get("tool_calls", 0)
        for tool, count in s.get("tools_used", {}).items():
            tool_totals[tool] += count
        total_duration += s.get("duration_mins") or 0

    return {
        "project": project_slug,
        "session_count": len(sessions),
        "total_duration_mins": round(total_duration, 1),
        "tokens": total_tokens,
        "estimated_cost_usd": round(total_cost, 4),
        "total_tool_calls": total_tool_calls,
        "tools_used": dict(sorted(tool_totals.items(), key=lambda x: -x[1])),
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
