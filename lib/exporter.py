import io
import pandas as pd

DAY_ORDER = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5}

FIELD_COLS = [
    "agent_name", "day", "beat_id", "store_id", "store_name",
    "gcu", "city", "locality", "cohort", "mtd_delivered", "last_delivered_date",
]

CALLER_COLS = [
    "agent_name", "store_id", "store_name",
    "gcu", "city", "locality", "cohort", "mtd_delivered", "last_delivered_date",
]


def build_field_csv(beats: list, day_assignments: dict, beat_agents: dict) -> bytes:
    rows = []
    for beat in beats:
        bid = beat["beat_id"]
        day = day_assignments.get(bid, "Unassigned")
        if day in ("Unassigned", "Caller", ""):
            continue
        agent = beat_agents.get(bid, beat["assigned_agent"])
        for _, row in beat["stores"].iterrows():
            rows.append({
                "agent_name": agent,
                "day": day,
                "beat_id": bid,
                "store_id": row.get("store_id", ""),
                "store_name": row.get("store_name", ""),
                "gcu": row.get("gcu", ""),
                "city": row.get("city", ""),
                "locality": row.get("locality", ""),
                "cohort": row.get("cohort", ""),
                "mtd_delivered": row.get("MTD Delivered", ""),
                "last_delivered_date": row.get("Last Delivered Order Date", ""),
            })

    df = pd.DataFrame(rows, columns=FIELD_COLS)
    df["_day_order"] = df["day"].map(DAY_ORDER).fillna(99)
    df = df.sort_values(["agent_name", "_day_order", "beat_id", "store_id"]).drop(columns=["_day_order"])

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()


def build_caller_csv(p2_stores, caller_agents: list) -> bytes:
    if p2_stores.empty:
        df = pd.DataFrame(columns=CALLER_COLS)
        buf = io.BytesIO()
        df.to_csv(buf, index=False)
        return buf.getvalue()

    # Round-robin assign P2 stores to caller agents
    rows = []
    callers = caller_agents if caller_agents else ["Unassigned"]
    for i, (_, row) in enumerate(p2_stores.iterrows()):
        assigned_caller = callers[i % len(callers)]
        rows.append({
            "agent_name": assigned_caller,
            "store_id": row.get("store_id", ""),
            "store_name": row.get("store_name", ""),
            "gcu": row.get("gcu", ""),
            "city": row.get("city", ""),
            "locality": row.get("locality", ""),
            "cohort": row.get("cohort", ""),
            "mtd_delivered": row.get("MTD Delivered", ""),
            "last_delivered_date": row.get("Last Delivered Order Date", ""),
        })

    df = pd.DataFrame(rows, columns=CALLER_COLS)

    buf = io.BytesIO()
    df.to_csv(buf, index=False)
    return buf.getvalue()
