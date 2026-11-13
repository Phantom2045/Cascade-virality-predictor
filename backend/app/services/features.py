"""Early-window structural and temporal feature extraction (no text or user features)."""

from __future__ import annotations

import math
from typing import Final

import networkx as nx
import numpy as np
import pandas as pd

from app.services.graph import assert_no_future_events, build_cascade_graph, truncate_to_window

FEATURE_NAMES: Final[tuple[str, ...]] = (
    "num_nodes",
    "num_edges",
    "max_degree",
    "avg_degree",
    "degree_variance",
    "max_depth",
    "avg_depth",
    "max_branching",
    "avg_branching",
    "density",
    "clustering_coefficient",
    "num_leaves",
    "leaf_ratio",
    "num_components",
    "structural_virality",
    "event_rate",
    "time_to_third_event",
    "median_inter_event_gap",
)


def compute_structural_virality(
    graph: nx.DiGraph,
    *,
    exact_max_nodes: int = 500,
    sample_sources: int = 128,
    seed: int = 42,
) -> float:
    """Compute Wiener-index mean pairwise distance on the largest weakly connected component."""
    if graph.number_of_nodes() <= 1:
        return 0.0

    undirected = graph.to_undirected()
    largest_nodes = max(nx.connected_components(undirected), key=len)
    n = len(largest_nodes)
    if n <= 1:
        return 0.0

    sub = undirected.subgraph(largest_nodes)
    if n <= exact_max_nodes:
        total_dist = 0
        for node in sub.nodes:
            lengths = nx.single_source_shortest_path_length(sub, node)
            total_dist += sum(lengths.values())
        return float(total_dist / (n * (n - 1)))

    # Deterministic source sampling for very large early graphs
    rng = np.random.default_rng(seed)
    nodes_list = sorted(str(x) for x in sub.nodes)
    k = min(sample_sources, n)
    chosen_indices = rng.choice(n, size=k, replace=False)
    sample_means: list[float] = []
    for idx in chosen_indices:
        src = nodes_list[int(idx)]
        lengths = nx.single_source_shortest_path_length(sub, src)
        sample_means.append(float(sum(lengths.values())) / float(n - 1))
    return float(np.mean(sample_means))


def extract_cascade_features(
    cascade_df: pd.DataFrame,
    window_seconds: float,
    *,
    exact_max_nodes: int = 500,
    sample_sources: int = 128,
    seed: int = 42,
) -> dict[str, float]:
    """Extract all 18 structural and time-aware features from early-window edges only."""
    early_df = truncate_to_window(cascade_df, window_seconds)
    assert_no_future_events(early_df, window_seconds)

    info = build_cascade_graph(early_df)
    g = info.graph
    num_nodes = int(g.number_of_nodes())
    num_edges = int(g.number_of_edges())

    if num_nodes == 0:
        return {
            name: (math.nan if name == "time_to_third_event" else 0.0)
            for name in FEATURE_NAMES
        }

    undirected = g.to_undirected()
    degrees = [float(d) for _, d in undirected.degree()]
    max_degree = float(max(degrees))
    avg_degree = float(np.mean(degrees))
    degree_variance = float(np.var(degrees, ddof=0))

    depth_values = [float(info.depths[str(n)]) for n in g.nodes]
    max_depth = float(max(depth_values))
    avg_depth = float(np.mean(depth_values))

    out_degrees = [int(g.out_degree(n)) for n in g.nodes]
    max_branching = float(max(out_degrees))
    internal_out = [float(d) for d in out_degrees if d > 0]
    avg_branching = float(np.mean(internal_out)) if internal_out else 0.0

    density = float(nx.density(g)) if num_nodes > 1 else 0.0
    clustering_coefficient = float(nx.average_clustering(undirected))

    num_leaves = len(info.leaves)
    leaf_ratio = float(num_leaves) / float(num_nodes)
    num_components = int(nx.number_weakly_connected_components(g))
    structural_virality = compute_structural_virality(
        g,
        exact_max_nodes=exact_max_nodes,
        sample_sources=sample_sources,
        seed=seed,
    )

    # Time-aware early features strictly from in-window events
    edge_rows = early_df.loc[early_df["parent_id"].notna()]
    edge_times = sorted(float(t) for t in edge_rows["timestamp"].tolist())
    all_times = sorted(float(t) for t in early_df["timestamp"].tolist())
    t0 = all_times[0] if all_times else 0.0

    if edge_times:
        span = max(edge_times[-1] - t0, 1.0)
        event_rate = float(len(edge_times)) / span
        timeline = [t0, *edge_times] if t0 <= edge_times[0] else edge_times
        gaps = np.diff(np.asarray(timeline, dtype=float))
        median_inter_event_gap = float(np.median(gaps)) if len(gaps) > 0 else 0.0
        time_to_third_event = (
            float(edge_times[2] - t0) if len(edge_times) >= 3 else math.nan
        )
    else:
        event_rate = 0.0
        median_inter_event_gap = 0.0
        time_to_third_event = math.nan

    return {
        "num_nodes": float(num_nodes),
        "num_edges": float(num_edges),
        "max_degree": max_degree,
        "avg_degree": avg_degree,
        "degree_variance": degree_variance,
        "max_depth": max_depth,
        "avg_depth": avg_depth,
        "max_branching": max_branching,
        "avg_branching": avg_branching,
        "density": density,
        "clustering_coefficient": clustering_coefficient,
        "num_leaves": float(num_leaves),
        "leaf_ratio": leaf_ratio,
        "num_components": float(num_components),
        "structural_virality": structural_virality,
        "event_rate": event_rate,
        "time_to_third_event": time_to_third_event,
        "median_inter_event_gap": median_inter_event_gap,
    }


def extract_features_table(
    edges_df: pd.DataFrame,
    window_seconds: float,
    *,
    exact_max_nodes: int = 500,
    sample_sources: int = 128,
    seed: int = 42,
) -> pd.DataFrame:
    """Compute early-window feature matrix indexed by cascade_id."""
    early_df = truncate_to_window(edges_df, window_seconds)
    assert_no_future_events(early_df, window_seconds)

    all_cascade_ids = sorted(edges_df["cascade_id"].astype(str).unique().tolist())
    grouped = {str(cid): grp for cid, grp in early_df.groupby("cascade_id", sort=False)}

    rows: list[dict[str, float | str]] = []
    for cid in all_cascade_ids:
        grp = grouped.get(cid)
        if grp is None:
            feats = {
                name: (math.nan if name == "time_to_third_event" else 0.0)
                for name in FEATURE_NAMES
            }
        else:
            feats = extract_cascade_features(
                grp,
                window_seconds=window_seconds,
                exact_max_nodes=exact_max_nodes,
                sample_sources=sample_sources,
                seed=seed,
            )
        row: dict[str, float | str] = {"cascade_id": cid}
        row.update(feats)
        rows.append(row)

    return pd.DataFrame(rows, columns=["cascade_id", *FEATURE_NAMES])
