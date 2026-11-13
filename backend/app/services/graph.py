"""Propagation graph construction, early-window truncation, and tree serialization."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

import networkx as nx
import pandas as pd

from app.errors import FutureEventLeakageError
from app.schemas import TreeEdgePayload, TreeGraphResponse, TreeNodePayload


@dataclass(frozen=True)
class CascadeGraphInfo:
    """Constructed propagation graph and topological summaries."""

    graph: nx.DiGraph
    roots: list[str]
    leaves: list[str]
    depths: dict[str, int]
    node_timestamps: dict[str, float]


def assert_no_future_events(df: pd.DataFrame, max_timestamp: float) -> None:
    """Guard against future-event leakage beyond early window T."""
    if df.empty:
        return
    max_observed = float(df["timestamp"].max())
    if max_observed > float(max_timestamp):
        raise FutureEventLeakageError(
            f"Leakage detected: event timestamp {max_observed} exceeds window {max_timestamp}."
        )


def truncate_to_window(df: pd.DataFrame, window_seconds: float) -> pd.DataFrame:
    """Keep strictly edges/events with timestamp <= window_seconds."""
    if df.empty:
        return df.copy()
    truncated = df.loc[df["timestamp"] <= float(window_seconds)].copy()
    assert_no_future_events(truncated, window_seconds)
    return truncated


def build_cascade_graph(cascade_df: pd.DataFrame) -> CascadeGraphInfo:
    """Build a directed propagation graph (parent -> child) from validated cascade rows."""
    graph = nx.DiGraph()
    node_timestamps: dict[str, float] = {}

    if cascade_df.empty:
        return CascadeGraphInfo(
            graph=graph, roots=[], leaves=[], depths={}, node_timestamps={}
        )

    ordered = cascade_df.sort_values(by=["timestamp", "child_id"], kind="mergesort")
    for row in ordered.itertuples(index=False):
        parent_id = row.parent_id
        child_id = str(row.child_id)
        ts = float(row.timestamp)

        if child_id not in node_timestamps or ts < node_timestamps[child_id]:
            node_timestamps[child_id] = ts
        if not graph.has_node(child_id):
            graph.add_node(child_id, timestamp=node_timestamps[child_id])

        if parent_id is not None and not (isinstance(parent_id, float) and pd.isna(parent_id)):
            p_str = str(parent_id)
            if p_str not in node_timestamps:
                # If parent wasn't explicitly declared, assign 0.0 or earliest edge time <= ts
                node_timestamps[p_str] = 0.0 if ts >= 0.0 else ts
            if not graph.has_node(p_str):
                graph.add_node(p_str, timestamp=node_timestamps[p_str])
            if p_str != child_id:
                graph.add_edge(p_str, child_id, timestamp=ts)

    roots = sorted(
        [str(n) for n in graph.nodes if graph.in_degree(n) == 0],
        key=lambda n: (node_timestamps.get(n, 0.0), n),
    )
    if not roots and graph.number_of_nodes() > 0:
        # Fallback if cyclic component has no in-degree-0 node
        fallback = min(graph.nodes, key=lambda n: (node_timestamps.get(str(n), 0.0), str(n)))
        roots = [str(fallback)]

    depths: dict[str, int] = {}
    queue: deque[str] = deque()
    for r in roots:
        depths[r] = 0
        queue.append(r)

    while queue:
        curr = queue.popleft()
        curr_depth = depths[curr]
        children = sorted(
            [str(nbr) for nbr in graph.successors(curr)],
            key=lambda n: (node_timestamps.get(n, 0.0), n),
        )
        for nxt in children:
            if nxt not in depths:
                depths[nxt] = curr_depth + 1
                queue.append(nxt)

    # Handle any detached cyclic component unreachable from primary roots
    for n in sorted([str(x) for x in graph.nodes], key=lambda x: (node_timestamps.get(x, 0.0), x)):
        if n not in depths:
            depths[n] = 0
            queue.append(n)
            while queue:
                curr = queue.popleft()
                for nxt in graph.successors(curr):
                    nxt_s = str(nxt)
                    if nxt_s not in depths:
                        depths[nxt_s] = depths[curr] + 1
                        queue.append(nxt_s)

    leaves = sorted(
        [str(n) for n in graph.nodes if graph.out_degree(n) == 0],
        key=lambda n: (node_timestamps.get(n, 0.0), n),
    )
    return CascadeGraphInfo(
        graph=graph,
        roots=roots,
        leaves=leaves,
        depths=depths,
        node_timestamps=node_timestamps,
    )


def serialize_tree_for_api(
    cascade_id: str,
    cascade_df: pd.DataFrame,
    window_seconds: float,
    stats: dict[str, float],
    max_nodes: int = 1000,
) -> TreeGraphResponse:
    """Serialize early-window propagation tree for the Analyze view, capping huge trees."""
    early_df = truncate_to_window(cascade_df, window_seconds)
    info = build_cascade_graph(early_df)
    g = info.graph

    total_nodes = int(g.number_of_nodes())
    total_edges = int(g.number_of_edges())
    root_id = info.roots[0] if info.roots else None

    # Order nodes in BFS order from roots so truncation preserves the upper/early tree
    ordered_nodes: list[str] = []
    seen: set[str] = set()
    q: deque[str] = deque(info.roots)
    for r in info.roots:
        seen.add(r)

    while q and len(ordered_nodes) < max_nodes:
        curr = q.popleft()
        ordered_nodes.append(curr)
        children = sorted(
            [str(nbr) for nbr in g.successors(curr)],
            key=lambda n: (info.node_timestamps.get(n, 0.0), n),
        )
        for ch in children:
            if ch not in seen:
                seen.add(ch)
                q.append(ch)

    if len(ordered_nodes) < min(total_nodes, max_nodes):
        remaining = sorted(
            [str(x) for x in g.nodes],
            key=lambda x: (info.node_timestamps.get(x, 0.0), x),
        )
        for n in remaining:
            if n not in seen:
                seen.add(n)
                ordered_nodes.append(n)
                if len(ordered_nodes) >= max_nodes:
                    break

    kept = set(ordered_nodes)
    truncated = total_nodes > len(ordered_nodes)
    notice = (
        f"Tree has {total_nodes} early-window nodes; showing the first "
        f"{len(ordered_nodes)} nodes in BFS order."
        if truncated
        else None
    )

    root_set = set(info.roots)
    leaf_set = set(info.leaves)
    nodes_payload: list[TreeNodePayload] = []
    for nid in ordered_nodes:
        preds = [str(p) for p in g.predecessors(nid) if str(p) in kept]
        nodes_payload.append(
            TreeNodePayload(
                id=nid,
                parent_id=preds[0] if preds else None,
                timestamp=float(info.node_timestamps.get(nid, 0.0)),
                depth=int(info.depths.get(nid, 0)),
                is_root=nid in root_set,
                is_leaf=nid in leaf_set,
                out_degree=int(g.out_degree(nid)),
            )
        )

    edges_payload: list[TreeEdgePayload] = []
    for u, v, data in g.edges(data=True):
        us, vs = str(u), str(v)
        if us in kept and vs in kept:
            edges_payload.append(
                TreeEdgePayload(
                    parent_id=us,
                    child_id=vs,
                    timestamp=float(data.get("timestamp", 0.0)),
                )
            )
    edges_payload.sort(key=lambda e: (e.timestamp, e.parent_id, e.child_id))

    return TreeGraphResponse(
        cascade_id=cascade_id,
        early_window_seconds=window_seconds,
        root_id=root_id,
        total_nodes=total_nodes,
        total_edges=total_edges,
        returned_nodes=len(nodes_payload),
        truncated=truncated,
        truncation_notice=notice,
        nodes=nodes_payload,
        edges=edges_payload,
        stats=stats,
    )
