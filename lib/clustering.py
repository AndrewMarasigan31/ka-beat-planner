import math
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

MAX_BEAT_RADIUS_KM = 50  # fallback only; threshold is data-driven (median + 1.5× IQR)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in kilometres between two lat/lon points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def _flag_isolated_stores(df: pd.DataFrame) -> pd.Index:
    """Return index of stores whose nearest neighbor is a statistical outlier in distance.
    Uses median + 1.5×IQR of all nearest-neighbor distances as the isolation threshold."""
    coords = df[["lat", "lng"]].values
    nn_dists = []
    for i, (lat, lng) in enumerate(coords):
        dists = [
            haversine_km(lat, lng, coords[j][0], coords[j][1])
            for j in range(len(coords)) if j != i
        ]
        nn_dists.append(min(dists) if dists else 0.0)

    nn_arr = np.array(nn_dists)
    q1, q3 = np.percentile(nn_arr, [25, 75])
    iqr = q3 - q1
    threshold_km = q3 + 1.5 * iqr

    isolated_mask = nn_arr > threshold_km
    return df.index[isolated_mask]


def run_clustering(stores_df: pd.DataFrame, beat_size: int, field_agents: list) -> dict:
    """Cluster stores geographically and assign to field agents."""
    df = stores_df.dropna(subset=["lat", "lng"]).copy()

    coords = df[["lat", "lng"]].values
    k = max(1, math.ceil(len(df) / beat_size))
    km = KMeans(n_clusters=k, init="k-means++", n_init=10, random_state=42)
    df["_cluster"] = km.fit_predict(coords)
    centroids = km.cluster_centers_  # shape (k, 2)

    # Merge small clusters (< beat_size * 0.5) into nearest neighbor
    cluster_sizes = df["_cluster"].value_counts()
    small = cluster_sizes[cluster_sizes < beat_size * 0.5].index.tolist()
    for sc in small:
        sc_centroid = centroids[sc]
        dists = [
            (np.linalg.norm(sc_centroid - centroids[c]), c)
            for c in range(k)
            if c != sc and c not in small
        ]
        if dists:
            _, nearest = min(dists)
            df.loc[df["_cluster"] == sc, "_cluster"] = nearest

    # Re-split any cluster that exceeds beat_size after merging — repeat until none remain oversized
    next_cluster_id = int(df["_cluster"].max()) + 1
    changed = True
    while changed:
        changed = False
        oversized = df["_cluster"].value_counts()
        oversized = oversized[oversized > beat_size].index.tolist()
        for oc in oversized:
            oc_df = df[df["_cluster"] == oc]
            sub_k = max(2, math.ceil(len(oc_df) / beat_size))
            sub_km = KMeans(n_clusters=sub_k, init="k-means++", n_init=10, random_state=42)
            sub_labels = sub_km.fit_predict(oc_df[["lat", "lng"]].values)
            new_ids = [oc if label == 0 else next_cluster_id + label - 1 for label in sub_labels]
            next_cluster_id += sub_k - 1
            df.loc[df["_cluster"] == oc, "_cluster"] = new_ids
            changed = True

    # Assign each cluster to nearest field agent by centroid proximity
    agent_coords = _build_agent_coords(stores_df, field_agents)

    # Compute per-cluster centroid after merge
    cluster_ids = df["_cluster"].unique()
    cluster_centroid = {
        cid: df[df["_cluster"] == cid][["lat", "lng"]].values.mean(axis=0)
        for cid in cluster_ids
    }

    cluster_agent = {}
    for cid, centroid in cluster_centroid.items():
        if agent_coords:
            dists = {a: np.linalg.norm(centroid - ac) for a, ac in agent_coords.items()}
            cluster_agent[cid] = min(dists, key=dists.get)
        else:
            cluster_agent[cid] = field_agents[0] if field_agents else "Unknown"

    df["_agent"] = df["_cluster"].map(cluster_agent)

    # P2 detection: cluster-level, not store-level.
    # Compute each cluster's distance to its assigned agent's home territory.
    # Use median + 1.5×IQR as the outlier threshold so only genuinely isolated
    # clusters go to callers — not just clusters that happen to be far in km terms.
    cluster_dist_km = {}
    for cid, centroid in cluster_centroid.items():
        agent = cluster_agent.get(cid)
        if agent and agent in agent_coords:
            agent_home = agent_coords[agent]
            cluster_dist_km[cid] = haversine_km(centroid[0], centroid[1], agent_home[0], agent_home[1])
        else:
            cluster_dist_km[cid] = 0.0

    dists = list(cluster_dist_km.values())
    if len(dists) >= 4:
        q1, q3 = np.percentile(dists, [25, 75])
        iqr = q3 - q1
        p2_threshold_km = q3 + 1.5 * iqr
    else:
        p2_threshold_km = MAX_BEAT_RADIUS_KM

    p2_clusters = {cid for cid, d in cluster_dist_km.items() if d > p2_threshold_km}

    # P2 routing disabled — all stores assigned to field agents for now
    p2_stores = pd.DataFrame(columns=df.columns)
    p1_df = df

    beats = []
    beat_counter = 1
    for cid in sorted(p1_df["_cluster"].unique()):
        cluster_df = p1_df[p1_df["_cluster"] == cid].drop(columns=["_cluster", "_agent"])
        agent = cluster_agent.get(cid, field_agents[0] if field_agents else "Unknown")
        beat_id = f"B{beat_counter:03d}"
        beats.append({"beat_id": beat_id, "assigned_agent": agent, "stores": cluster_df})
        beat_counter += 1

    return {"beats": beats, "p2_stores": p2_stores, "caller_agents": []}


def _build_agent_coords(stores_df: pd.DataFrame, field_agents: list) -> dict:
    """Compute each field agent's mean coordinate from their assigned stores."""
    result = {}
    for agent in field_agents:
        subset = stores_df[stores_df["agent"] == agent].dropna(subset=["lat", "lng"])
        if not subset.empty:
            result[agent] = subset[["lat", "lng"]].values.mean(axis=0)
    return result
