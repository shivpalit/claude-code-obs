# claude-obs

Query Claude Code session data — token usage, estimated costs, tool patterns, and session history.

## Usage

```
/claude-obs [command] [options]
```

## Commands

**List projects**
```
claude-obs projects
claude-obs projects --output table
```

**List sessions**
```
claude-obs sessions --project=-home-myproject --output table --limit 10
claude-obs sessions --project=-home-myproject --sort created
```

**Session detail**
```
claude-obs session --latest --project=-home-myproject
claude-obs session <session-uuid> --project=-home-myproject
```

**Aggregate stats** (tokens, cost, tool breakdown across all sessions)
```
claude-obs stats --project=-home-myproject
```

**Search sessions**
```
claude-obs search "keyword" --project=-home-myproject
```

**Launch dashboard**
```
claude-obs --webapp
```

## Finding your project slug

Run `claude-obs projects` to list all slugs. The slug is your working directory path with `/` replaced by `-`. Example: `/home/me/myproject` → `-home-me-myproject`.

Use `--project=<slug>` (with `=`) when the slug starts with `-`.

## Cost estimates

Estimated using Claude Sonnet 4.6 API pricing. Useful as a relative measure of work done — not actual billing.
