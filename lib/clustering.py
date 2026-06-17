import math
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans


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

    # P2 detection: distance to own cluster centroid > mean inter-centroid distance
    all_centroids = list(cluster_centroid.values())
    inter_dists = []
    for i in range(len(all_centroids)):
        for j in range(i + 1, len(all_centroids)):
            inter_dists.append(np.linalg.norm(all_centroids[i] - all_centroids[j]))
    mean_inter = np.mean(inter_dists) if inter_dists else float("inf")

    def dist_to_centroid(row):
        c = cluster_centroid.get(row["_cluster"])
        if c is None:
            return 0.0
        return np.linalg.norm(np.array([row["lat"], row["lng"]]) - c)

    df["_dist"] = df.apply(dist_to_centroid, axis=1)
    p2_mask = df["_dist"] > mean_inter

    p2_stores = df[p2_mask].drop(columns=["_cluster", "_agent", "_dist"])
    p1_df = df[~p2_mask]

    beats = []
    beat_counter = 1
    for cid in sorted(p1_df["_cluster"].unique()):
        cluster_df = p1_df[p1_df["_cluster"] == cid].drop(columns=["_cluster", "_agent", "_dist"])
        agent = cluster_agent.get(cid, field_agents[0] if field_agents else "Unknown")
        beat_id = f"B{beat_counter:03d}"
        beats.append({"beat_id": beat_id, "assigned_agent": agent, "stores": cluster_df})
        beat_counter += 1

    return {"beats": beats, "p2_stores": p2_stores}


def _build_agent_coords(stores_df: pd.DataFrame, field_agents: list) -> dict:
    """Compute each field agent's mean coordinate from their assigned stores."""
    result = {}
    for agent in field_agents:
        subset = stores_df[stores_df["agent"] == agent].dropna(subset=["lat", "lng"])
        if not subset.empty:
            result[agent] = subset[["lat", "lng"]].values.mean(axis=0)
    return result
