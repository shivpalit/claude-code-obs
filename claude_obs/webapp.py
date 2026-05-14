import streamlit as st

from .core import aggregate_stats, list_projects, list_sessions

st.set_page_config(page_title="claude-obs", page_icon="🔭", layout="wide")

st.title("claude-obs")
st.caption("Claude Code session observability")

projects = list_projects()
project_options = [p["slug"] for p in projects]

if not project_options:
    st.error("No Claude Code projects found in ~/.claude/projects/")
    st.stop()

selected = st.selectbox(
    "Project",
    options=project_options,
    format_func=lambda s: s,
)

sessions = list_sessions(selected)

st.subheader(f"Sessions ({len(sessions)})")

rows = [
    {
        "Title": s.get("title") or "—",
        "Started": (s.get("started_at") or "")[:19].replace("T", " "),
        "Duration (min)": s.get("duration_mins") or 0,
        "Tool calls": s.get("tool_calls") or 0,
        "Est. cost ($)": s.get("estimated_cost_usd") or 0,
        "session_id": s["session_id"],
    }
    for s in sessions
]

st.dataframe(
    rows,
    width="stretch",
    hide_index=True,
    column_order=["Title", "Started", "Duration (min)", "Tool calls", "Est. cost ($)"],
)
