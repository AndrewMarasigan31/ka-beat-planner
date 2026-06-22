import pandas as pd
import folium
import streamlit as st
from folium.plugins import Draw
from shapely.geometry import Point, shape
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


def build_map(beats: list, p2_stores: pd.DataFrame, agent_colors: dict, beat_colors: dict = None, excluded_ids: set = None, draw: bool = False) -> folium.Map:
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

    excluded_ids = excluded_ids or set()

    for beat in beats:
        color = (beat_colors or {}).get(beat["beat_id"], agent_colors.get(beat["assigned_agent"], "#888888"))
        for _, row in beat["stores"].iterrows():
            if pd.isna(row["lat"]) or pd.isna(row["lng"]):
                continue
            if row.get("store_id") in excluded_ids:
                continue  # rendered as grey diamond via p2_stores
            pending_flag = " ⏳ Pending order" if row.get("has_pending") else ""
            popup_html = (
                f"<b>{row.get('store_name', '')}</b>{pending_flag}<br>"
                f"Agent: {beat['assigned_agent']}<br>"
                f"Beat: {beat['beat_id']}<br>"
                f"Cohort: {row.get('cohort', '')}<br>"
                f"MTD Delivered: ₱{row.get('MTD Delivered', 0):,.0f}<br>"
                f"Pending GMV: ₱{row.get('Pending GMV MTD', 0):,.0f}<br>"
                f"Last Placed: {row.get('Last Placed Order Date', '') or '—'}<br>"
                f"Last Delivered: {row.get('Last Delivered Order Date', '') or '—'}"
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
        caller = row.get("_caller_agent", "Caller")
        caller_label = "Excluded from beat" if caller == "Excluded" else f"Caller: {caller}"
        pending_flag = " ⏳ Pending order" if row.get("has_pending") else ""
        popup_html = (
            f"<b>{row.get('store_name', '')}</b>{pending_flag}<br>"
            f"{caller_label}<br>"
            f"Cohort: {row.get('cohort', '')}<br>"
            f"MTD Delivered: ₱{row.get('MTD Delivered', 0):,.0f}<br>"
            f"Pending GMV: ₱{row.get('Pending GMV MTD', 0):,.0f}<br>"
            f"Last Placed: {row.get('Last Placed Order Date', '') or '—'}<br>"
            f"Last Delivered: {row.get('Last Delivered Order Date', '') or '—'}"
        )
        folium.Marker(
            location=[row["lat"], row["lng"]],
            icon=folium.DivIcon(
                html='<div style="width:10px;height:10px;background:#888;transform:rotate(45deg);opacity:0.85;border:1px solid #555;"></div>',
                icon_size=(10, 10),
                icon_anchor=(5, 5),
            ),
            popup=folium.Popup(popup_html, max_width=260),
        ).add_to(m)

    if all_lats and all_lngs:
        m.fit_bounds([[min(all_lats), min(all_lngs)], [max(all_lats), max(all_lngs)]])

    if draw:
        Draw(
            export=False,
            draw_options={
                "polygon": True,
                "rectangle": True,
                "circle": False,
                "marker": False,
                "circlemarker": False,
                "polyline": False,
            },
            edit_options={"edit": True, "remove": True},
        ).add_to(m)

    return m


if not check_password():
    st.stop()

st.title("KA Beat Planner")

# ── Upload ──────────────────────────────────────────────────────────────────
_upload_open = st.session_state.get("parsed") is None
with st.expander("📂 Upload", expanded=_upload_open):
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
            excluded_ids = st.session_state.get("excluded_store_ids", set())
            stores_for_clustering = parsed["stores"]
            if excluded_ids:
                stores_for_clustering = stores_for_clustering[~stores_for_clustering["store_id"].isin(excluded_ids)]
            result = run_clustering(stores_for_clustering, int(beat_size), parsed["field_agents"])
            result["composed"] = compose_beats(result["beats"], int(beat_size))

            # Assign P2 stores to caller agents round-robin so map can color them
            caller_agents = sorted(parsed["caller_agents"])
            if not result["p2_stores"].empty and caller_agents:
                p2 = result["p2_stores"].copy()
                p2["_caller_agent"] = [caller_agents[i % len(caller_agents)] for i in range(len(p2))]
                result["p2_stores"] = p2

            # Assign stable colors per beat (not per agent)
            BEAT_PALETTE = [
                "#E63946","#2A9D8F","#E9C46A","#F4A261","#264653",
                "#6A4C93","#1982C4","#8AC926","#FF595E","#FFCA3A",
                "#6BCB77","#4D96FF","#F72585","#7209B7","#3A0CA3",
                "#4CC9F0","#FB8500","#023047","#8ECAE6","#219EBC",
            ]
            beat_colors = {b["beat_id"]: BEAT_PALETTE[i % len(BEAT_PALETTE)] for i, b in enumerate(result["beats"])}
            result["beat_colors"] = beat_colors
            result["agent_colors"] = {}
            st.session_state["clustering"] = result
            st.session_state.pop("day_assignments", None)
            st.session_state.pop("beat_agents", None)

        clustering = st.session_state.get("clustering")
        if clustering:
            beats = clustering["beats"]
            p2 = clustering["p2_stores"]
            agent_colors = clustering.get("agent_colors", {})
            beat_colors = clustering.get("beat_colors", {})

            # ── Excluded stores → effective P2 ────────────────────────────────
            if "excluded_store_ids" not in st.session_state:
                st.session_state["excluded_store_ids"] = set()
            if "excluded_store_history" not in st.session_state:
                st.session_state["excluded_store_history"] = []
            excluded_ids = st.session_state["excluded_store_ids"]

            if excluded_ids:
                all_store_rows = []
                for b in beats:
                    all_store_rows.append(b["stores"])
                all_beat_stores_df = pd.concat(all_store_rows, ignore_index=True) if all_store_rows else pd.DataFrame()
                excl_df = all_beat_stores_df[all_beat_stores_df["store_id"].isin(excluded_ids)].copy() if not all_beat_stores_df.empty else pd.DataFrame()
                if not excl_df.empty:
                    excl_df["_caller_agent"] = "Excluded"
                effective_p2 = pd.concat([p2, excl_df], ignore_index=True) if not excl_df.empty else p2
            else:
                effective_p2 = p2

            beat_counts = {}
            store_counts = {}
            for b in beats:
                a = b["assigned_agent"]
                beat_counts[a] = beat_counts.get(a, 0) + 1
                store_counts[a] = store_counts.get(a, 0) + len(b["stores"])

            st.success(f"**{len(beats)}** beats · **{len(effective_p2)}** caller/excluded stores")
            rows = [{"agent": a, "beats": beat_counts[a], "# of stores": store_counts[a]} for a in beat_counts]
            st.dataframe(pd.DataFrame(rows).sort_values("agent"), use_container_width=True)

            # ── Filters ──────────────────────────────────────────────────────
            field_agents_sorted = sorted({b["assigned_agent"] for b in beats})
            caller_agents_sorted = sorted(effective_p2["_caller_agent"].dropna().unique().tolist()) if "_caller_agent" in effective_p2.columns else []
            all_agents_sorted = field_agents_sorted + (["── Callers ──"] + caller_agents_sorted if caller_agents_sorted else [])

            filter_col1, filter_col2 = st.columns(2)

            with filter_col1:
                agent_filter = st.selectbox(
                    "Agent",
                    options=["All Agents"] + all_agents_sorted,
                    key="map_agent_filter",
                )

            is_caller_filter = agent_filter in caller_agents_sorted

            # Narrow beat options by selected agent (only for field agents)
            if agent_filter == "All Agents" or is_caller_filter:
                beats_for_filter = beats
            else:
                beats_for_filter = [b for b in beats if b["assigned_agent"] == agent_filter]

            beat_options = ["All Beats"] + sorted(b["beat_id"] for b in beats_for_filter)

            with filter_col2:
                beat_filter = st.selectbox(
                    "Beat",
                    options=beat_options,
                    key="map_beat_filter",
                    disabled=is_caller_filter,
                )

            # Apply filters
            if is_caller_filter:
                filtered_beats = []
                filtered_p2 = effective_p2[effective_p2["_caller_agent"] == agent_filter] if "_caller_agent" in effective_p2.columns else effective_p2
            elif agent_filter == "All Agents":
                filtered_beats = beats
                filtered_p2 = effective_p2
            else:
                filtered_beats = [b for b in beats_for_filter if beat_filter == "All Beats" or b["beat_id"] == beat_filter]
                filtered_p2 = pd.DataFrame()

            # ── Map ───────────────────────────────────────────────────────────
            fmap = build_map(filtered_beats, filtered_p2, agent_colors, beat_colors, excluded_ids=excluded_ids, draw=True)
            map_output = st_folium(fmap, use_container_width=True, height=600)

            # Process lasso: find stores inside drawn polygons
            drawn = (map_output or {}).get("all_drawings") or []
            if drawn:
                newly_excluded = set()
                all_beat_stores = [(row, beat) for beat in filtered_beats for _, row in beat["stores"].iterrows()]
                for feature in drawn:
                    try:
                        geom = shape(feature["geometry"])
                        for row, _ in all_beat_stores:
                            if pd.notna(row.get("lat")) and pd.notna(row.get("lng")):
                                if geom.contains(Point(row["lng"], row["lat"])):
                                    newly_excluded.add(row["store_id"])
                    except Exception:
                        pass
                if newly_excluded - excluded_ids:
                    st.session_state["excluded_store_history"].append(frozenset(excluded_ids))
                    st.session_state["excluded_store_ids"] = excluded_ids | newly_excluded
                    st.rerun()

            col_excl1, col_excl2, col_excl3 = st.columns([3, 1, 1])
            with col_excl1:
                if excluded_ids:
                    st.warning(f"✕ {len(excluded_ids)} store(s) excluded from beats")
            with col_excl2:
                history = st.session_state.get("excluded_store_history", [])
                if history and st.button("↩ Undo"):
                    st.session_state["excluded_store_ids"] = set(history.pop())
                    st.session_state["excluded_store_history"] = history
                    st.rerun()
            with col_excl3:
                if excluded_ids and st.button("Clear all"):
                    st.session_state["excluded_store_history"].append(frozenset(excluded_ids))
                    st.session_state["excluded_store_ids"] = set()
                    st.rerun()

            # ── Store Table ───────────────────────────────────────────────────
            table_rows = []
            for b in filtered_beats:
                df_b = b["stores"].copy()
                df_b.insert(0, "beat_id", b["beat_id"])
                df_b.insert(1, "assigned_agent", b["assigned_agent"])
                table_rows.append(df_b)

            with st.expander("📋 Store Table", expanded=False):
                if is_caller_filter:
                    caller_display_cols = [c for c in [
                        "_caller_agent", "store_name", "gcu", "city", "locality",
                        "cohort", "MTD Delivered", "Pending GMV MTD", "has_pending",
                        "Last Placed Order Date", "Last Delivered Order Date",
                    ] if c in filtered_p2.columns]
                    st.dataframe(filtered_p2[caller_display_cols].rename(columns={"_caller_agent": "caller_agent"}), use_container_width=True)
                elif table_rows:
                    table_df = pd.concat(table_rows, ignore_index=True)
                    display_cols = [c for c in [
                        "beat_id", "assigned_agent", "store_name", "gcu", "city", "locality",
                        "cohort", "MTD Delivered", "Pending GMV MTD", "has_pending",
                        "Last Placed Order Date", "Last Delivered Order Date",
                    ] if c in table_df.columns]
                    st.dataframe(table_df[display_cols], use_container_width=True)
                else:
                    st.info("No stores to display.")

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

        CALLER_OPTION = "→ Caller"
        agent_dropdown_options = all_agents_full + [CALLER_OPTION]

        # Initialize day_assignments and beat_agents in session_state
        if "day_assignments" not in st.session_state:
            st.session_state["day_assignments"] = {b["beat_id"]: "Unassigned" for b in beats}
        if "beat_agents" not in st.session_state:
            st.session_state["beat_agents"] = {b["beat_id"]: b["assigned_agent"] for b in beats}

        day_assignments = st.session_state["day_assignments"]
        beat_agents = st.session_state["beat_agents"]

        st.subheader("Beat assignments")

        # Inherit agent filter from Beat Planner above
        map_agent_filter = st.session_state.get("map_agent_filter", "All Agents")
        if map_agent_filter and map_agent_filter != "All Agents":
            active_filter = map_agent_filter
            st.caption(f"Filtered to: **{active_filter}** (set in Beat Planner above)")
        else:
            active_filter = None

        filtered_beats_da = [
            b for b in beats
            if active_filter is None or beat_agents.get(b["beat_id"]) == active_filter
        ]

        st.caption(f"Showing {len(filtered_beats_da)} of {len(beats)} beats")

        # Header row
        h1, h2, h3, h4 = st.columns([2, 2, 3, 2])
        h1.markdown("**Beat**")
        h2.markdown("**Stores**")
        h3.markdown("**Agent**")
        h4.markdown("**Day**")

        for beat in sorted(filtered_beats_da, key=lambda b: b["beat_id"]):
            bid = beat["beat_id"]
            is_caller_beat = beat_agents.get(bid) == CALLER_OPTION
            c1, c2, c3, c4 = st.columns([2, 2, 3, 2])
            with c1:
                st.write(bid)
            with c2:
                st.write(len(beat["stores"]))
            with c3:
                current = beat_agents.get(bid, all_agents_full[0] if all_agents_full else CALLER_OPTION)
                idx = agent_dropdown_options.index(current) if current in agent_dropdown_options else 0
                new_agent = st.selectbox(
                    "Agent",
                    options=agent_dropdown_options,
                    index=idx,
                    key=f"agent_{bid}",
                    label_visibility="collapsed",
                )
                beat_agents[bid] = new_agent
            with c4:
                if is_caller_beat:
                    st.caption("Caller")
                    day_assignments[bid] = "Caller"
                else:
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

        # Summary grid: field agents × day
        st.subheader("Summary: stores per agent per day")
        grid_rows = []
        for agent in all_agents_full:
            row = {"Agent": agent}
            for day in [d for d in DAYS if d != "Unassigned"]:
                agent_beats_on_day = [
                    b for b in beats
                    if beat_agents.get(b["beat_id"]) == agent and day_assignments.get(b["beat_id"]) == day
                ]
                count = sum(len(b["stores"]) for b in agent_beats_on_day)
                row[day] = count if count > 0 else ""
            grid_rows.append(row)
        grid_df = pd.DataFrame(grid_rows)

        caller_beat_count = sum(1 for a in beat_agents.values() if a == CALLER_OPTION)
        unassigned_beats = [bid for bid, d in day_assignments.items() if d == "Unassigned" and beat_agents.get(bid) != CALLER_OPTION]
        if caller_beat_count:
            st.info(f"📞 {caller_beat_count} beat(s) routed to callers")
        if unassigned_beats:
            st.warning(f"⚠️ {len(unassigned_beats)} field beat(s) still need a day: {', '.join(unassigned_beats)}")

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
        caller_agents = parsed["caller_agents"] if parsed else []

        # Beats marked "→ Caller" by supervisor become P2
        CALLER_OPTION = "→ Caller"
        field_beats = [b for b in beats if beat_agents.get(b["beat_id"]) != CALLER_OPTION]
        caller_beats = [b for b in beats if beat_agents.get(b["beat_id"]) == CALLER_OPTION]

        # Collect all stores from caller beats into a flat dataframe
        caller_store_frames = [b["stores"].assign(_caller_beat=b["beat_id"]) for b in caller_beats]
        p2 = pd.concat(caller_store_frames, ignore_index=True) if caller_store_frames else pd.DataFrame()

        # Lasso-excluded stores: collect rows first, then strip from field beats
        excluded_ids = st.session_state.get("excluded_store_ids", set())
        if excluded_ids:
            all_beat_frames = pd.concat([b["stores"] for b in beats], ignore_index=True)
            excl_rows = all_beat_frames[all_beat_frames["store_id"].isin(excluded_ids)].drop_duplicates("store_id")
            if not excl_rows.empty:
                p2 = pd.concat([p2, excl_rows], ignore_index=True)
            field_beats = [
                {**b, "stores": b["stores"][~b["stores"]["store_id"].isin(excluded_ids)]}
                for b in field_beats
            ]

        unassigned = [bid for bid, d in day_assignments.items() if d == "Unassigned" and beat_agents.get(bid) != CALLER_OPTION]
        export_disabled = False

        if unassigned:
            st.info(f"ℹ️ {len(unassigned)} beat(s) without a day will be skipped in the field export.")

        today = datetime.date.today().strftime("%Y-%m-%d")

        field_csv = build_field_csv(field_beats, day_assignments, beat_agents)
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
