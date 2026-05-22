# claude-code-obs

Observability for [Claude Code](https://claude.ai/code) sessions — inspect token usage, estimated costs, tool patterns, and session history from your local `.claude/` directory.

## Features

- **Python API** — import and query session data programmatically
- **CLI** — `claude-obs` command with projects, sessions, session detail, stats, and search
- **Streamlit dashboard** — visual charts for cost per session and tool usage breakdown
- **Claude Code skill** — install as a skill to query sessions from within Claude

## Requirements

- Python 3.11+
- Claude Code installed and used (sessions stored in `~/.claude/projects/`)

## Installation

```bash
git clone https://github.com/shivpalit/claude-code-obs
cd claude-code-obs
pip install -e .
```

## Python API

```python
from claude_obs import list_projects, list_sessions, get_session, get_session_messages, aggregate_stats, find_sessions

# List all Claude Code projects
list_projects()

# List sessions for a project (sorted by last activity)
list_sessions("-home-myproject")

# Get full detail for a session
get_session("-home-myproject", "<session-uuid>")

# Get all messages from a session
get_session_messages("-home-myproject", "<session-uuid>")

# Aggregate token/cost/tool stats across all sessions
aggregate_stats("-home-myproject")

# Search sessions by title or first message
find_sessions("-home-myproject", "portfolio")
```

## CLI

```bash
# List projects
claude-obs projects --output table

# List sessions (most recent 10)
claude-obs sessions --project=-home-myproject --output table --limit 10

# Detail for the latest session
claude-obs session --latest --project=-home-myproject

# Aggregate stats
claude-obs stats --project=-home-myproject

# Search
claude-obs search "portfolio" --project=-home-myproject

# Launch Streamlit dashboard
claude-obs --webapp
```

### Flags

| Flag | Description |
|------|-------------|
| `--project` | Project slug (use `=` syntax if slug starts with `-`) |
| `--output` | `json` (default) or `table` |
| `--limit` | Max sessions to return |
| `--sort` | `last_message` (default) or `created` |
| `--latest` | Use most recently active session |
| `--webapp` | Launch Streamlit dashboard |

## Streamlit dashboard

```bash
claude-obs --webapp
```

Shows cost per session chart, tool usage breakdown, session detail view, and a full sessions table with cost and duration formatting.

## Claude Code skill

Install the bundled skill so you can query session data from within Claude:

```bash
claude-obs install-skill
```

Then use `/claude-obs` in any Claude Code session.

## Project slug

Claude Code stores sessions under `~/.claude/projects/<slug>/` where the slug is your working directory path with `/` replaced by `-`. For `/home/me/myproject` the slug is `-home-me-myproject`.

Run `claude-obs projects` to see all slugs.

## Cost estimates

Costs are estimated using Claude Sonnet 4.6 API pricing and are useful as a relative measure of work done, not actual billing (especially if you're on a Max subscription).
