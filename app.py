import pandas as pd
import folium
import streamlit as st
from streamlit_folium import st_folium

from lib.parser import parse_xlsx
from lib.clustering import run_clustering
from lib.composer import compose_beats
from lib.exporter import build_field_csv, build_caller_csv

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

            # ── Filters ──────────────────────────────────────────────────────
            all_agents_sorted = sorted({b["assigned_agent"] for b in beats})
            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                agent_filter = st.selectbox(
                    "Agent",
                    options=["All Agents"] + all_agents_sorted,
                    key="map_agent_filter",
                )

            # Narrow beat options by selected agent
            if agent_filter == "All Agents":
                beats_for_filter = beats
            else:
                beats_for_filter = [b for b in beats if b["assigned_agent"] == agent_filter]

            beat_options = ["All Beats"] + sorted(b["beat_id"] for b in beats_for_filter)

            with filter_col2:
                beat_filter = st.selectbox(
                    "Beat",
                    options=beat_options,
                    key="map_beat_filter",
                )

            # Apply filters
            filtered_beats = beats_for_filter
            if beat_filter != "All Beats":
                filtered_beats = [b for b in filtered_beats if b["beat_id"] == beat_filter]

            # ── Map ───────────────────────────────────────────────────────────
            fmap = build_map(filtered_beats, p2 if agent_filter == "All Agents" and beat_filter == "All Beats" else pd.DataFrame(), agent_colors)
            st_folium(fmap, use_container_width=True, height=600)

            # ── Store Table ───────────────────────────────────────────────────
            table_rows = []
            for b in filtered_beats:
                df_b = b["stores"].copy()
                df_b.insert(0, "beat_id", b["beat_id"])
                df_b.insert(1, "assigned_agent", b["assigned_agent"])
                table_rows.append(df_b)

            if table_rows:
                table_df = pd.concat(table_rows, ignore_index=True)
                st.dataframe(table_df, use_container_width=True)

# ── Day Assignment ───────────────────────────────────────────────────────────
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Unassigned"]

with st.expander("📅 Day Assignment", expanded=False):
    clustering = st.session_state.get("clustering")
    parsed = st.session_state.get("parsed")
    if not clustering:
        st.info("Run clustering first.")
    else:
        beats = clustering["beats"]
        all_agents = sorted({b["assigned_agent"] for b in beats})
        if parsed:
            all_agents_full = sorted(parsed["field_agents"])
        else:
            all_agents_full = all_agents

        # Initialize day_assignments and beat_agents in session_state
        if "day_assignments" not in st.session_state:
            st.session_state["day_assignments"] = {b["beat_id"]: "Unassigned" for b in beats}
        if "beat_agents" not in st.session_state:
            st.session_state["beat_agents"] = {b["beat_id"]: b["assigned_agent"] for b in beats}

        day_assignments = st.session_state["day_assignments"]
        beat_agents = st.session_state["beat_agents"]

        st.subheader("Beat assignments")
        for agent in all_agents_full:
            agent_beats = [b for b in beats if beat_agents.get(b["beat_id"]) == agent]
            if not agent_beats:
                continue
            st.markdown(f"**{agent}**")
            for beat in agent_beats:
                bid = beat["beat_id"]
                col1, col2, col3 = st.columns([2, 3, 2])
                with col1:
                    st.write(bid)
                with col2:
                    new_agent = st.selectbox(
                        "Agent",
                        options=all_agents_full,
                        index=all_agents_full.index(beat_agents[bid]) if beat_agents[bid] in all_agents_full else 0,
                        key=f"agent_{bid}",
                        label_visibility="collapsed",
                    )
                    beat_agents[bid] = new_agent
                with col3:
                    new_day = st.selectbox(
                        "Day",
                        options=DAYS,
                        index=DAYS.index(day_assignments.get(bid, "Unassigned")),
                        key=f"day_{bid}",
                        label_visibility="collapsed",
                    )
                    day_assignments[bid] = new_day

        st.session_state["day_assignments"] = day_assignments
        st.session_state["beat_agents"] = beat_agents

        # Summary grid: agent × day
        st.subheader("Summary: stores per agent per day")
        grid_rows = []
        for agent in all_agents_full:
            row = {"Agent": agent}
            for day in DAYS:
                agent_beats_on_day = [
                    b for b in beats
                    if beat_agents.get(b["beat_id"]) == agent and day_assignments.get(b["beat_id"]) == day
                ]
                count = sum(len(b["stores"]) for b in agent_beats_on_day)
                row[day] = count if count > 0 else ""
            grid_rows.append(row)
        grid_df = pd.DataFrame(grid_rows)

        unassigned_beats = [bid for bid, d in day_assignments.items() if d == "Unassigned"]
        if unassigned_beats:
            st.warning(f"⚠️ {len(unassigned_beats)} beat(s) still unassigned: {', '.join(unassigned_beats)}")

        st.dataframe(grid_df, use_container_width=True)

# ── Export ───────────────────────────────────────────────────────────────────
import datetime

with st.expander("📥 Export", expanded=False):
    clustering = st.session_state.get("clustering")
    parsed = st.session_state.get("parsed")
    day_assignments = st.session_state.get("day_assignments", {})
    beat_agents = st.session_state.get("beat_agents", {})

    if not clustering:
        st.info("Run clustering and assign days first.")
    else:
        beats = clustering["beats"]
        p2 = clustering["p2_stores"]
        caller_agents = parsed["caller_agents"] if parsed else []

        unassigned = [bid for bid, d in day_assignments.items() if d == "Unassigned"]
        export_disabled = len(unassigned) > 0

        if export_disabled:
            st.warning(f"⚠️ {len(unassigned)} beat(s) unassigned — assign all days before exporting.")

        today = datetime.date.today().strftime("%Y-%m-%d")

        field_csv = build_field_csv(beats, day_assignments, beat_agents)
        st.download_button(
            label="⬇️ Download Field Agent Schedule",
            data=field_csv,
            file_name=f"ka_field_schedule_{today}.csv",
            mime="text/csv",
            disabled=export_disabled,
        )

        caller_csv = build_caller_csv(p2, caller_agents)
        st.download_button(
            label="⬇️ Download Caller List (P2 stores)",
            data=caller_csv,
            file_name=f"ka_caller_list_{today}.csv",
            mime="text/csv",
            disabled=export_disabled,
        )
