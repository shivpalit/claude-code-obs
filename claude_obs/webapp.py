import pandas as pd
import streamlit as st

from .core import aggregate_stats, get_session, list_projects, list_sessions

st.set_page_config(page_title="claude-obs", page_icon="🔭", layout="wide")

st.title("claude-obs")
st.caption("Claude Code session observability")

projects = list_projects()
project_options = [p["slug"] for p in projects]

if not project_options:
    st.error("No Claude Code projects found in ~/.claude/projects/")
    st.stop()

selected = st.selectbox("Project", options=project_options)

sessions = list_sessions(selected)
stats = aggregate_stats(selected)

# --- Summary metrics ---
col1, col2, col3, col4 = st.columns(4)
col1.metric("Sessions", stats["session_count"])
col2.metric("Est. cost", f"${stats['estimated_cost_usd']:.2f}")
col3.metric("Tool calls", stats["total_tool_calls"])
col4.metric("Duration", f"{stats['total_duration_mins']:.0f} min")

st.divider()

# --- Cost per session chart ---
st.subheader("Cost per session")
df = pd.DataFrame([
    {
        "session": (s.get("title") or s["session_id"][:8]),
        "cost": s.get("estimated_cost_usd") or 0,
        "date": (s.get("started_at") or "")[:10],
    }
    for s in sessions
]).sort_values("date")

if not df.empty:
    st.bar_chart(df.set_index("session")["cost"], height=250)

st.divider()

# --- Tool usage ---
st.subheader("Tool usage")
tools = stats.get("tools_used", {})
if tools:
    tool_df = pd.DataFrame(list(tools.items()), columns=["tool", "calls"]).sort_values("calls", ascending=False)
    st.bar_chart(tool_df.set_index("tool")["calls"], height=250)

st.divider()

# --- Sessions table + detail ---
st.subheader(f"Sessions ({len(sessions)})")

session_labels = {s["session_id"]: (s.get("title") or s["session_id"][:8]) for s in sessions}
chosen_id = st.selectbox("View session detail", options=["—"] + list(session_labels.keys()), format_func=lambda x: session_labels.get(x, x))

if chosen_id and chosen_id != "—":
    detail = get_session(selected, chosen_id)
    d1, d2, d3, d4 = st.columns(4)
    d1.metric("Duration", f"{detail.get('duration_mins') or 0} min")
    d2.metric("Tool calls", detail.get("tool_calls") or 0)
    d3.metric("Est. cost", f"${detail.get('estimated_cost_usd') or 0:.4f}")
    d4.metric("Messages", f"{detail.get('user_messages', 0)}u / {detail.get('assistant_messages', 0)}a")
    with st.expander("Tokens"):
        st.json(detail.get("tokens", {}))
    with st.expander("Tools used"):
        st.json(detail.get("tools_used", {}))

st.divider()

rows = [
    {
        "Title": s.get("title") or "—",
        "Started": (s.get("started_at") or "")[:19].replace("T", " "),
        "Duration (min)": s.get("duration_mins") or 0,
        "Tool calls": s.get("tool_calls") or 0,
        "Est. cost ($)": s.get("estimated_cost_usd") or 0,
    }
    for s in sessions
]
st.dataframe(rows, width="stretch", hide_index=True)
