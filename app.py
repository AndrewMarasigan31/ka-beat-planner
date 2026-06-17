import streamlit as st

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

with st.expander("📂 Upload", expanded=True):
    st.info("Upload your store list XLSX here.")

with st.expander("🗺️ Beat Planner", expanded=False):
    st.info("Configure and run beat clustering here.")

with st.expander("📥 Export", expanded=False):
    st.info("Download field agent schedules and caller lists here.")
