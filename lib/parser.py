import pandas as pd

REQUIRED_COLUMNS = [
    "store_id",
    "store_name",
    "agent",
    "gcu",
    "warehouse",
    "point_y",
    "point_x",
    "visit_day",
    "cohort",
    "MTD Delivered",
    "Last Delivered Order Date",
]

FIELD_PREFIXES = ("[SKAS/", "[GKAS/")
CALLER_PREFIX = "[Caller/KA]"


def parse_xlsx(file) -> dict:
    """Parse uploaded XLSX, classify agents, validate columns."""
    errors = []

    try:
        df = pd.read_excel(file, engine="openpyxl")
    except Exception as e:
        return {"stores": pd.DataFrame(), "field_agents": [], "caller_agents": [], "errors": [str(e)]}

    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        errors.append(f"Missing columns: {', '.join(missing)}")
        return {"stores": df, "field_agents": [], "caller_agents": [], "errors": errors}

    df = df.rename(columns={"point_y": "lat", "point_x": "lng"})
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lng"] = pd.to_numeric(df["lng"], errors="coerce")

    all_agents = df["agent"].dropna().unique().tolist()
    field_agents = [a for a in all_agents if str(a).startswith(FIELD_PREFIXES)]
    caller_agents = [a for a in all_agents if str(a).startswith(CALLER_PREFIX)]

    return {
        "stores": df,
        "field_agents": sorted(field_agents),
        "caller_agents": sorted(caller_agents),
        "errors": errors,
    }
