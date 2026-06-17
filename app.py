import streamlit as st
from lib.parser import parse_xlsx
from lib.clustering import run_clustering
from lib.composer import compose_beats

st.set_page_config(
    page_title="KA Beat Planner",
    page_icon="📍",
    layout="wide",
)

PASSWORD = "ka2026"


def check_password() -> bool:
    if st.session_state.get("authenticated"):
        return True
    st.title("KA Beat Planner")
    pwd = st.text_input("Enter password", type="password", key="pwd_input")
    if pwd:
        if pwd == PASSWORD:
            st.session_state["authenticated"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    return False


if not check_password():
    st.stop()

st.title("KA Beat Planner")

# ── Upload ──────────────────────────────────────────────────────────────────
with st.expander("📂 Upload", expanded=True):
    uploaded = st.file_uploader("Upload store list XLSX", type=["xlsx"])

    if uploaded:
        parsed = parse_xlsx(uploaded)
        if parsed["errors"]:
            for err in parsed["errors"]:
                st.error(err)
        else:
            st.session_state["parsed"] = parsed
            df = parsed["stores"]
            st.success(
                f"Loaded **{len(df)}** stores · "
                f"**{len(parsed['field_agents'])}** field agents · "
                f"**{len(parsed['caller_agents'])}** caller agents"
            )
            counts = df[df["agent"].isin(parsed["field_agents"])].groupby("agent").size().reset_index(name="stores")
            st.dataframe(counts, use_container_width=True)

# ── Beat Planner ─────────────────────────────────────────────────────────────
with st.expander("🗺️ Beat Planner", expanded=False):
    parsed = st.session_state.get("parsed")
    if not parsed:
        st.info("Upload a store list first.")
    else:
        beat_size = st.number_input("Beat size (stores per beat)", min_value=5, max_value=100, value=30, step=1)

        if st.button("Run Clustering"):
            result = run_clustering(parsed["stores"], int(beat_size), parsed["field_agents"])
            result["composed"] = compose_beats(result["beats"], int(beat_size))
            st.session_state["clustering"] = result

        clustering = st.session_state.get("clustering")
        if clustering:
            beats = clustering["beats"]
            p2 = clustering["p2_stores"]

            beat_counts = {}
            for b in beats:
                a = b["assigned_agent"]
                beat_counts[a] = beat_counts.get(a, 0) + 1

            st.success(f"**{len(beats)}** beats · **{len(p2)}** P2 stores sent to callers")

            rows = [{"agent": a, "beats": c} for a, c in beat_counts.items()]
            import pandas as pd
            st.dataframe(pd.DataFrame(rows).sort_values("agent"), use_container_width=True)

# ── Export ───────────────────────────────────────────────────────────────────
with st.expander("📥 Export", expanded=False):
    st.info("Download field agent schedules and caller lists here.")
