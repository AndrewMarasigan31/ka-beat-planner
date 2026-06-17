import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium

from lib.parser import parse_xlsx
from lib.clustering import run_clustering
from lib.composer import compose_beats

st.set_page_config(
    page_title="KA Beat Planner",
    page_icon="📍",
    layout="wide",
)

PASSWORD = "ka2026"
AGENT_PALETTE = [
    "#E63946", "#2A9D8F", "#E9C46A", "#F4A261", "#264653",
    "#6A4C93", "#1982C4", "#8AC926", "#FF595E",
]


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


def build_map(beats: list, p2_stores: pd.DataFrame, agent_colors: dict) -> folium.Map:
    all_lats, all_lngs = [], []

    for beat in beats:
        df = beat["stores"]
        all_lats += df["lat"].dropna().tolist()
        all_lngs += df["lng"].dropna().tolist()

    if not p2_stores.empty:
        all_lats += p2_stores["lat"].dropna().tolist()
        all_lngs += p2_stores["lng"].dropna().tolist()

    center_lat = sum(all_lats) / len(all_lats) if all_lats else 14.5
    center_lng = sum(all_lngs) / len(all_lngs) if all_lngs else 121.0

    m = folium.Map(location=[center_lat, center_lng], zoom_start=11)

    for beat in beats:
        color = agent_colors.get(beat["assigned_agent"], "#888888")
        for _, row in beat["stores"].iterrows():
            if pd.isna(row["lat"]) or pd.isna(row["lng"]):
                continue
            popup_html = (
                f"<b>{row.get('store_name', '')}</b><br>"
                f"Agent: {beat['assigned_agent']}<br>"
                f"Beat: {beat['beat_id']}<br>"
                f"Cohort: {row.get('cohort', '')}<br>"
                f"MTD Delivered: {row.get('MTD Delivered', '')}<br>"
                f"Last Delivered: {row.get('Last Delivered Order Date', '')}"
            )
            folium.CircleMarker(
                location=[row["lat"], row["lng"]],
                radius=6,
                color=color,
                fill=True,
                fill_color=color,
                fill_opacity=0.8,
                popup=folium.Popup(popup_html, max_width=260),
            ).add_to(m)

    for _, row in p2_stores.iterrows():
        if pd.isna(row["lat"]) or pd.isna(row["lng"]):
            continue
        popup_html = (
            f"<b>{row.get('store_name', '')}</b><br>"
            f"P2 — assigned to callers<br>"
            f"Cohort: {row.get('cohort', '')}<br>"
            f"MTD Delivered: {row.get('MTD Delivered', '')}<br>"
            f"Last Delivered: {row.get('Last Delivered Order Date', '')}"
        )
        folium.CircleMarker(
            location=[row["lat"], row["lng"]],
            radius=5,
            color="#888888",
            fill=True,
            fill_color="#888888",
            fill_opacity=0.6,
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(m)

    if all_lats and all_lngs:
        m.fit_bounds([[min(all_lats), min(all_lngs)], [max(all_lats), max(all_lngs)]])

    return m


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
            # Assign stable colors per agent
            agents = sorted({b["assigned_agent"] for b in result["beats"]})
            result["agent_colors"] = {a: AGENT_PALETTE[i % len(AGENT_PALETTE)] for i, a in enumerate(agents)}
            st.session_state["clustering"] = result

        clustering = st.session_state.get("clustering")
        if clustering:
            beats = clustering["beats"]
            p2 = clustering["p2_stores"]
            agent_colors = clustering.get("agent_colors", {})

            beat_counts = {}
            for b in beats:
                a = b["assigned_agent"]
                beat_counts[a] = beat_counts.get(a, 0) + 1

            st.success(f"**{len(beats)}** beats · **{len(p2)}** P2 stores sent to callers")
            rows = [{"agent": a, "beats": c} for a, c in beat_counts.items()]
            st.dataframe(pd.DataFrame(rows).sort_values("agent"), use_container_width=True)

            fmap = build_map(beats, p2, agent_colors)
            st_folium(fmap, use_container_width=True, height=600)

# ── Export ───────────────────────────────────────────────────────────────────
with st.expander("📥 Export", expanded=False):
    st.info("Download field agent schedules and caller lists here.")
