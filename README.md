# claude-code-obs

Observability for [Claude Code](https://claude.ai/code) sessions — inspect token usage, estimated costs, tool patterns, and session history from your local `.claude/` directory.

## Requirements

- Python 3.11+
- Claude Code installed and used (sessions stored in `~/.claude/projects/`)

## Installation

```bash
pip install -e .
```

Or clone and install:

```bash
git clone https://github.com/shivpalit/claude-code-obs
cd claude-code-obs
pip install -e .
```

## Python API

```python
from claude_obs import list_projects, list_sessions, get_session, aggregate_stats, find_sessions

# List all Claude Code projects
list_projects()

# List sessions for a project (sorted by last activity)
list_sessions("-home-myproject")

# Get full detail for a session
get_session("-home-myproject", "<session-uuid>")

# Aggregate token/cost/tool stats across all sessions
aggregate_stats("-home-myproject")

# Search sessions by title or first message
find_sessions("-home-myproject", "portfolio")
```

## CLI

```bash
# List projects
claude-obs projects

# List sessions (table output, most recent 10)
claude-obs sessions --project=-home-myproject --output table --limit 10

# Detail for the latest session
claude-obs session --latest --project=-home-myproject

# Aggregate stats
claude-obs stats --project=-home-myproject

# Search
claude-obs search "portfolio" --project=-home-myproject
```

### Flags

| Flag | Description |
|------|-------------|
| `--project` | Project slug (use `=` syntax if slug starts with `-`) |
| `--output` | `json` (default) or `table` |
| `--limit` | Max sessions to return |
| `--sort` | `last_message` (default) or `created` |
| `--latest` | Use most recently active session |

## Project slug

Claude Code stores sessions under `~/.claude/projects/<slug>/` where the slug is your working directory path with `/` replaced by `-`. For `/home/me/myproject` the slug is `-home-me-myproject`.

Run `claude-obs projects` to see all slugs.

## Cost estimates

Costs are estimated using Claude Sonnet 4.6 API pricing and are useful as a relative measure of work done, not actual billing (especially if you're on a Max subscription).
