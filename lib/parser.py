import datetime

import pandas as pd

REQUIRED_COLUMNS = [
    "store_id",
    "store_name",
    "store_username",
    "agent",
    "gcu",
    "warehouse",
    "point_y",
    "point_x",
    "visit_day",
    "cohort",
    "MTD Delivered",
    "Last Delivered Order Date",
    "Last Placed Order Date",
    "Pending GMV MTD",
]

FIELD_PREFIXES = ("[SKAS/", "[GKAS/")
CALLER_PREFIX = "[Caller/KA]"

_EXCEL_EPOCH = datetime.datetime(1899, 12, 30)


def _convert_date_col(series: pd.Series) -> pd.Series:
    """Convert a column that may contain Excel serial ints or strings to date strings (YYYY-MM-DD)."""
    def _to_date(val):
        if pd.isna(val):
            return None
        if isinstance(val, (int, float)):
            try:
                return (_EXCEL_EPOCH + datetime.timedelta(days=int(val))).strftime("%Y-%m-%d")
            except Exception:
                return None
        if isinstance(val, (datetime.datetime, datetime.date)):
            return pd.Timestamp(val).strftime("%Y-%m-%d")
        try:
            return pd.to_datetime(val).strftime("%Y-%m-%d")
        except Exception:
            return None
    return series.map(_to_date)


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

    df["Last Delivered Order Date"] = _convert_date_col(df["Last Delivered Order Date"])
    df["Last Placed Order Date"] = _convert_date_col(df["Last Placed Order Date"])

    df["MTD Delivered"] = pd.to_numeric(df["MTD Delivered"], errors="coerce").fillna(0)
    df["Pending GMV MTD"] = pd.to_numeric(df["Pending GMV MTD"], errors="coerce").fillna(0)
    df["has_pending"] = df["Pending GMV MTD"] > 0

    all_agents = df["agent"].dropna().unique().tolist()
    field_agents = [a for a in all_agents if str(a).startswith(FIELD_PREFIXES)]
    caller_agents = [a for a in all_agents if str(a).startswith(CALLER_PREFIX)]

    return {
        "stores": df,
        "field_agents": sorted(field_agents),
        "caller_agents": sorted(caller_agents),
        "errors": errors,
    }
