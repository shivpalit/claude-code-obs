# claude-code-obs

Observability for [Claude Code](https://claude.ai/code) sessions — inspect token usage, estimated costs, tool patterns, and session history from your local `.claude/` directory.

## Requirements

- Python 3.11+
- Claude Code installed with at least one session recorded (`~/.claude/projects/` must exist)

## Installation

```bash
pip install git+https://github.com/shivpalit/claude-code-obs
```

---

## Python API

Import and query session data directly in Python.

```python
from claude_obs import (
    list_projects,
    list_sessions,
    get_session,
    get_session_messages,
    aggregate_stats,
    find_sessions,
)
```

**List all Claude Code projects**
```python
list_projects()
# [{"slug": "-home-myproject", "path": "/home/myproject", "session_count": 12, "last_active": "..."}]
```

**List sessions for a project**
```python
list_sessions("-home-myproject")                        # sorted by last activity
list_sessions("-home-myproject", sort="created")        # sorted by start time
```

**Get full detail for a session**
```python
get_session("-home-myproject", "<session-uuid>")
```

**Get all messages from a session**
```python
get_session_messages("-home-myproject", "<session-uuid>")
```

**Aggregate stats across all sessions in a project**
```python
aggregate_stats("-home-myproject")
# {"session_count": 42, "estimated_cost_usd": 12.34, "total_tool_calls": 890, "tools_used": {...}, ...}
```

**Search sessions by title or opening message**
```python
find_sessions("-home-myproject", "portfolio")
```

### Project slugs

Claude Code stores sessions under `~/.claude/projects/<slug>/` where the slug is your working directory path with `/` replaced by `-`. For `/home/me/myproject` the slug is `-home-me-myproject`.

Use `--project=<slug>` (with `=`) on the CLI when the slug starts with `-`.

### Cost estimates

Costs are fetched live from the Anthropic pricing page and applied per-model. Falls back to hardcoded rates if the fetch fails. Useful as a relative measure of work done — not actual billing (especially on a Max subscription).

---

## CLI

The `claude-obs` CLI provides the same functionality from the terminal.

```
claude-obs <command> [options]
```

**List projects**
```bash
claude-obs projects
claude-obs projects --output table
```

**List sessions**
```bash
claude-obs sessions --project=-home-myproject
claude-obs sessions --project=-home-myproject --output table --limit 10
claude-obs sessions --project=-home-myproject --sort created
```

**Session detail**
```bash
claude-obs session --latest --project=-home-myproject
claude-obs session <session-uuid> --project=-home-myproject
```

**Aggregate stats**
```bash
claude-obs stats --project=-home-myproject
```

**Search sessions**
```bash
claude-obs search "portfolio" --project=-home-myproject
claude-obs search "portfolio" --project=-home-myproject --output table
```

### Flags

| Flag | Applies to | Description |
|------|-----------|-------------|
| `--project` | sessions, session, stats, search | Project slug. Use `=` syntax if slug starts with `-` |
| `--output` | projects, sessions, search | `json` (default) or `table` |
| `--limit` | sessions | Max sessions to return |
| `--sort` | sessions | `last_message` (default) or `created` |
| `--latest` | session | Use most recently active session |

---

## Streamlit Dashboard

Launch an interactive dashboard to explore session data visually.

```bash
claude-obs --webapp
```

The dashboard includes:
- **Summary metrics** — session count, total estimated cost, tool calls, duration
- **Cost per session** — bar chart sorted by date
- **Tool usage** — breakdown of which tools were used most across all sessions
- **Session detail** — click into any session to see token breakdown, tool usage, and metadata
- **Sessions table** — full sortable table with cost and duration formatting

---

## Claude Code Skill

Install `claude-obs` as a Claude Code skill so you can query session data directly within any Claude conversation.

```bash
claude-obs install-skill
```

Run this from inside a Claude Code project directory to get the option to install globally or project-locally:

```
Claude project detected: /home/me/myproject
  [1] Global  (~/.claude/skills/claude-obs/)  [default]
  [2] Project (/home/me/myproject/.claude/skills/claude-obs/)
Choice [1/2, Enter=global]:
```

The installed skill is generated dynamically with the exact path to your `claude-obs` binary — no venv activation needed. It also writes a `paths.json` alongside `SKILL.md` tracking the installed version and Python path, so re-running `install-skill` will warn you if the version or environment has changed.

Once installed, use `/claude-obs` in any Claude Code session.
