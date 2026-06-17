import streamlit as st
from lib.parser import parse_xlsx

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
    st.info("Configure and run beat clustering here.")

# ── Export ───────────────────────────────────────────────────────────────────
with st.expander("📥 Export", expanded=False):
    st.info("Download field agent schedules and caller lists here.")
