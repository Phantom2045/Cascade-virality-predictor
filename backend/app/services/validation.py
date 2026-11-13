"""Canonical edge CSV parsing, schema validation, and explicit cleaning."""

from __future__ import annotations

import io
from typing import Any

import networkx as nx
import numpy as np
import pandas as pd

from app.errors import InvalidInputError
from app.schemas import CANONICAL_COLUMNS, ValidationReport

_NULL_PARENT_TOKENS = {"", "nan", "none", "null", "na", "n/a"}


def _normalize_id(val: Any) -> str | None:
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    text = str(val).strip()
    if text.lower() in _NULL_PARENT_TOKENS:
        return None
    return text


def parse_canonical_csv(raw_bytes: bytes) -> pd.DataFrame:
    """Decode and parse an uploaded CSV file into a raw DataFrame."""
    if not raw_bytes.strip():
        raise InvalidInputError("Uploaded CSV file is empty.")
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidInputError("CSV file must be UTF-8 encoded.") from exc

    try:
        df = pd.read_csv(
            io.StringIO(text),
            dtype={"cascade_id": str, "parent_id": str, "child_id": str},
        )
    except Exception as exc:
        raise InvalidInputError(f"Failed to parse CSV: {exc}") from exc

    missing = [col for col in CANONICAL_COLUMNS if col not in df.columns]
    if missing:
        raise InvalidInputError(
            "CSV is missing required canonical columns.",
            details={"missing_columns": missing, "required_columns": list(CANONICAL_COLUMNS)},
        )
    if df.empty:
        raise InvalidInputError("Uploaded CSV contains headers but zero edge rows.")
    return df


def _break_cascade_cycles(edges_df: pd.DataFrame) -> tuple[pd.DataFrame, int, int]:
    """Detect directed cycles per cascade and remove the latest-timestamp edge in each cycle."""
    if edges_df.empty:
        return edges_df, 0, 0

    drop_indices: set[int] = set()
    cycles_detected = 0

    for _cascade_id, group in edges_df.groupby("cascade_id", sort=False):
        graph = nx.DiGraph()
        edge_meta: dict[tuple[str, str], tuple[float, int]] = {}
        for idx, row in group.iterrows():
            u = str(row["parent_id"])
            v = str(row["child_id"])
            ts = float(row["timestamp"])
            graph.add_edge(u, v)
            edge_meta[(u, v)] = (ts, int(idx))

        while True:
            try:
                cycle = nx.find_cycle(graph, orientation="original")
            except nx.NetworkXNoCycle:
                break
            cycles_detected += 1
            # Choose the latest-timestamp edge in the cycle (deterministic tie-break on row index)
            worst_edge: tuple[str, str] | None = None
            worst_key: tuple[float, int] = (-float("inf"), -1)
            for u, v, _dir in cycle:
                key = edge_meta[(str(u), str(v))]
                if key > worst_key:
                    worst_key = key
                    worst_edge = (str(u), str(v))
            if worst_edge is None:
                break
            graph.remove_edge(*worst_edge)
            drop_indices.add(worst_key[1])

    if not drop_indices:
        return edges_df, 0, 0

    cleaned = edges_df.drop(index=list(drop_indices)).reset_index(drop=True)
    return cleaned, cycles_detected, len(drop_indices)


def validate_and_clean_edges(df: pd.DataFrame) -> tuple[pd.DataFrame, ValidationReport]:
    """Validate canonical edge DataFrame and clean structural issues explicitly.

    Rules enforced and reported:
    - Required columns: cascade_id, parent_id, child_id, timestamp.
    - Drop malformed rows (missing cascade_id, missing child_id, non-numeric/NaN/inf timestamp).
    - Drop negative timestamps (< 0).
    - Drop self-loops (parent_id == child_id).
    - Drop exact duplicate edges keeping the earliest timestamp.
    - Resolve multiple parents per (cascade_id, child_id) by keeping the earliest-timestamp parent.
    - Detect directed cycles and break them by removing the latest-timestamp edge in each cycle.
    - Flag cascades with multiple root declarations or multiple in-degree-0 nodes.
    """
    total_rows = int(len(df))
    missing = [col for col in CANONICAL_COLUMNS if col not in df.columns]
    if missing:
        report = ValidationReport(
            is_valid=False,
            total_rows=total_rows,
            valid_edges=0,
            cascades_count=0,
            missing_columns=missing,
            actions_taken=[],
            warnings=[f"Missing required columns: {', '.join(missing)}"],
        )
        return pd.DataFrame(columns=list(CANONICAL_COLUMNS)), report

    work = df.loc[:, list(CANONICAL_COLUMNS)].copy()
    work["cascade_id"] = work["cascade_id"].map(_normalize_id)
    work["parent_id"] = work["parent_id"].map(_normalize_id)
    work["child_id"] = work["child_id"].map(_normalize_id)
    work["timestamp"] = pd.to_numeric(work["timestamp"], errors="coerce")

    malformed_mask = (
        work["cascade_id"].isna()
        | work["child_id"].isna()
        | work["timestamp"].isna()
        | ~np.isfinite(work["timestamp"].astype(float))
    )
    malformed_rows_dropped = int(malformed_mask.sum())
    work = work.loc[~malformed_mask].copy()
    work["timestamp"] = work["timestamp"].astype(float)

    neg_mask = work["timestamp"] < 0.0
    negative_timestamps_dropped = int(neg_mask.sum())
    work = work.loc[~neg_mask].copy()

    self_loop_mask = work["parent_id"].notna() & (work["parent_id"] == work["child_id"])
    self_loops_dropped = int(self_loop_mask.sum())
    work = work.loc[~self_loop_mask].copy()

    # Separate explicit root markers (parent_id is None) from directed edges
    roots_df = work.loc[work["parent_id"].isna()].copy()
    edges_df = work.loc[work["parent_id"].notna()].copy()

    # Sort edges deterministically so earliest-timestamp parent always comes first
    edges_df = edges_df.sort_values(
        by=["cascade_id", "timestamp", "parent_id", "child_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    # Exact duplicate (cascade_id, parent_id, child_id)
    before_dup = len(edges_df)
    edges_df = edges_df.drop_duplicates(
        subset=["cascade_id", "parent_id", "child_id"], keep="first"
    ).reset_index(drop=True)
    duplicate_edges_dropped = int(before_dup - len(edges_df))

    # Multiple parents for same (cascade_id, child_id) -> keep earliest-timestamp parent
    before_mp = len(edges_df)
    edges_df = edges_df.drop_duplicates(
        subset=["cascade_id", "child_id"], keep="first"
    ).reset_index(drop=True)
    multiple_parents_resolved = int(before_mp - len(edges_df))

    # Break cycles deterministically
    edges_df, cycles_detected, cycle_edges_removed = _break_cascade_cycles(edges_df)

    # Deduplicate explicit root declarations per (cascade_id, child_id)
    roots_df = roots_df.sort_values(by=["cascade_id", "timestamp", "child_id"], kind="mergesort")
    before_root_dup = len(roots_df)
    roots_df = roots_df.drop_duplicates(subset=["cascade_id", "child_id"], keep="first")
    duplicate_edges_dropped += int(before_root_dup - len(roots_df))

    # If a node has a resolved parent edge, drop redundant root declaration for that node
    if not roots_df.empty and not edges_df.empty:
        child_keys = set(zip(edges_df["cascade_id"], edges_df["child_id"], strict=False))
        keep_root_mask = [
            (cid, chid) not in child_keys
            for cid, chid in zip(roots_df["cascade_id"], roots_df["child_id"], strict=False)
        ]
        roots_df = roots_df.loc[keep_root_mask].copy()

    combined = pd.concat([roots_df, edges_df], ignore_index=True)
    combined = combined.sort_values(
        by=["cascade_id", "timestamp", "child_id"],
        kind="mergesort",
    ).reset_index(drop=True)

    # Count cascades with multiple roots (explicit or in-degree-0 nodes)
    multiple_roots_cascades = 0
    for _cid, grp in combined.groupby("cascade_id", sort=False):
        children_with_parent = set(grp.loc[grp["parent_id"].notna(), "child_id"])
        all_nodes = set(grp["child_id"]) | set(grp.loc[grp["parent_id"].notna(), "parent_id"])
        in_deg_zero = all_nodes - children_with_parent
        if len(in_deg_zero) > 1:
            multiple_roots_cascades += 1

    actions_taken: list[str] = []
    warnings: list[str] = []
    if malformed_rows_dropped:
        actions_taken.append(
            f"Dropped {malformed_rows_dropped} malformed row(s) with missing IDs "
            "or invalid timestamps."
        )
    if negative_timestamps_dropped:
        actions_taken.append(
            f"Dropped {negative_timestamps_dropped} row(s) with negative timestamps (< 0)."
        )
    if self_loops_dropped:
        actions_taken.append(f"Dropped {self_loops_dropped} self-loop edge(s).")
    if duplicate_edges_dropped:
        actions_taken.append(
            f"Dropped {duplicate_edges_dropped} duplicate edge(s), keeping earliest timestamp."
        )
    if multiple_parents_resolved:
        actions_taken.append(
            f"Resolved {multiple_parents_resolved} multi-parent conflict(s) by "
            "retaining the earliest-timestamp parent."
        )
    if cycles_detected:
        actions_taken.append(
            f"Detected {cycles_detected} directed cycle(s) and removed "
            f"{cycle_edges_removed} latest-timestamp cycle edge(s)."
        )
    if multiple_roots_cascades:
        warnings.append(
            f"{multiple_roots_cascades} cascade(s) contain multiple roots "
            "(disconnected components / forest)."
        )

    cascades_count = int(combined["cascade_id"].nunique()) if not combined.empty else 0
    is_valid = cascades_count > 0
    valid_edges = (
        int(len(combined.loc[combined["parent_id"].notna()])) if not combined.empty else 0
    )

    report = ValidationReport(
        is_valid=is_valid,
        total_rows=total_rows,
        valid_edges=valid_edges,
        cascades_count=cascades_count,
        missing_columns=[],
        malformed_rows_dropped=malformed_rows_dropped,
        negative_timestamps_dropped=negative_timestamps_dropped,
        self_loops_dropped=self_loops_dropped,
        duplicate_edges_dropped=duplicate_edges_dropped,
        multiple_parents_resolved=multiple_parents_resolved,
        cycles_detected=cycles_detected,
        cycle_edges_removed=cycle_edges_removed,
        multiple_roots_cascades=multiple_roots_cascades,
        actions_taken=actions_taken,
        warnings=warnings,
    )
    return combined, report
