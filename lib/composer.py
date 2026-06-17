import pandas as pd

GMV_ORDER = {
    "Active But High GMV Store": 0,
    "Active But Low GMV Store": 1,
    "Inactive Store": 2,
}

SLOT_COUNT = {
    "Active But High GMV Store": 3,
    "Active But Low GMV Store": 2,
    "Inactive Store": 1,
}


def compose_beats(beats: list, beat_size: int) -> list:
    """Apply GMV priority, trim over-capacity, and expand stores into day-slots."""
    composed = []
    for beat in beats:
        df = beat["stores"].copy()
        beat_id = beat["beat_id"]
        agent = beat["assigned_agent"]

        df["_gmv_order"] = df["cohort"].map(GMV_ORDER).fillna(99)
        df = df.sort_values("_gmv_order")

        # Trim over-capacity: Inactive first, then Low GMV; High GMV never trimmed
        if len(df) > beat_size:
            high = df[df["cohort"] == "Active But High GMV Store"]
            low = df[df["cohort"] == "Active But Low GMV Store"]
            inactive = df[df["cohort"] == "Inactive Store"]

            capacity_left = beat_size - len(high)
            if capacity_left <= 0:
                low = low.iloc[0:0]
                inactive = inactive.iloc[0:0]
            else:
                capacity_left_for_low = capacity_left
                if len(low) > capacity_left_for_low:
                    inactive = inactive.iloc[0:0]
                    low = low.iloc[:capacity_left_for_low]
                else:
                    capacity_left_for_inactive = capacity_left - len(low)
                    inactive = inactive.iloc[:capacity_left_for_inactive]

            df = pd.concat([high, low, inactive])

        # Expand each store into its day-slots
        slots = []
        for _, row in df.iterrows():
            n_slots = SLOT_COUNT.get(row.get("cohort", ""), 1)
            for i in range(1, n_slots + 1):
                entry = row.to_dict()
                entry["slot_index"] = i
                entry["beat_id"] = beat_id
                slots.append(entry)

        df = df.drop(columns=["_gmv_order"], errors="ignore")

        composed.append({
            "beat_id": beat_id,
            "assigned_agent": agent,
            "stores": df,
            "slots": slots,
        })

    return composed
