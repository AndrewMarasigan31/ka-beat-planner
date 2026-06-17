import math
import pandas as pd
import pytest
from lib.clustering import haversine_km, run_clustering


# --- haversine_km ---

def test_haversine_same_point_is_zero():
    assert haversine_km(14.5995, 120.9842, 14.5995, 120.9842) == pytest.approx(0.0)


def test_haversine_known_distance():
    # Manila (14.5995, 120.9842) to ~10 km north (14.6895, 120.9842)
    # 0.09 degrees lat ≈ 10 km
    km = haversine_km(14.5995, 120.9842, 14.6895, 120.9842)
    assert 9.5 < km < 10.5


# --- run_clustering radius cap ---

def _make_stores(records):
    """Build a minimal stores DataFrame for clustering tests."""
    rows = []
    for r in records:
        rows.append({
            "store_id": r["store_id"],
            "store_name": r["store_name"],
            "agent": "[SKAS/Agent A]",
            "gcu": "GCU1",
            "warehouse": "WH1",
            "lat": r["lat"],
            "lng": r["lng"],
            "visit_day": "Mon",
            "cohort": "Active But Low GMV Store",
            "MTD Delivered": 0,
            "Last Delivered Order Date": "2026-01-01",
        })
    return pd.DataFrame(rows)


def test_store_within_8km_stays_p1():
    # All 6 stores tightly clustered near Manila — all well within 8 km of centroid
    base_lat, base_lng = 14.5995, 120.9842
    stores = _make_stores([
        {"store_id": i, "store_name": f"Store {i}", "lat": base_lat + i * 0.005, "lng": base_lng + i * 0.005}
        for i in range(6)
    ])
    result = run_clustering(stores, beat_size=10, field_agents=["[SKAS/Agent A]"])
    p2_ids = set(result["p2_stores"]["store_id"].tolist())
    assert not p2_ids, f"Expected no P2 stores, got {p2_ids}"


def test_store_beyond_8km_demoted_to_p2():
    # 5 stores tightly clustered near Manila + 1 store ~15 km away
    base_lat, base_lng = 14.5995, 120.9842
    tight = [
        {"store_id": i, "store_name": f"Store {i}", "lat": base_lat + i * 0.003, "lng": base_lng + i * 0.003}
        for i in range(5)
    ]
    # ~15 km north: 0.135 degrees lat ≈ 15 km
    outlier = {"store_id": 99, "store_name": "Far Store", "lat": base_lat + 0.135, "lng": base_lng}
    stores = _make_stores(tight + [outlier])
    result = run_clustering(stores, beat_size=10, field_agents=["[SKAS/Agent A]"])
    p2_ids = set(result["p2_stores"]["store_id"].tolist())
    assert 99 in p2_ids, f"Expected far store (id=99) in P2, got p2_ids={p2_ids}"
