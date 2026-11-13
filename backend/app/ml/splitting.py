"""Temporal and stratified-random cascade-level splitting with leakage assertions."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.model_selection import StratifiedShuffleSplit


@dataclass(frozen=True)
class SplitIndices:
    """Disjoint cascade ID sets for train, validation, and test splits."""

    train_ids: list[str]
    val_ids: list[str]
    test_ids: list[str]


def assert_disjoint_splits(splits: SplitIndices) -> None:
    """Verify zero cascade_id overlap across train, validation, and test."""
    train_set = set(splits.train_ids)
    val_set = set(splits.val_ids)
    test_set = set(splits.test_ids)
    if train_set & val_set or train_set & test_set or val_set & test_set:
        raise AssertionError("Cascade ID overlap detected across dataset splits.")


def temporal_cascade_split(
    cascade_metadata: pd.DataFrame,
    *,
    train_ratio: float = 0.70,
    val_ratio: float = 0.10,
) -> SplitIndices:
    """Split cascades chronologically by root_timestamp (70% train / 10% val / 20% test)."""
    if cascade_metadata.empty:
        return SplitIndices(train_ids=[], val_ids=[], test_ids=[])

    ordered = cascade_metadata.sort_values(
        by=["root_timestamp", "cascade_id"], kind="mergesort"
    ).reset_index(drop=True)
    n = len(ordered)
    if n < 3:
        raise ValueError(f"Need at least 3 cascades for train/val/test split, got {n}.")

    train_end = max(1, int(round(n * train_ratio)))
    val_end = max(train_end + 1, int(round(n * (train_ratio + val_ratio))))
    if val_end >= n:
        val_end = n - 1
        train_end = min(train_end, val_end - 1)

    train_ids = ordered.iloc[:train_end]["cascade_id"].astype(str).tolist()
    val_ids = ordered.iloc[train_end:val_end]["cascade_id"].astype(str).tolist()
    test_ids = ordered.iloc[val_end:]["cascade_id"].astype(str).tolist()

    splits = SplitIndices(train_ids=train_ids, val_ids=val_ids, test_ids=test_ids)
    assert_disjoint_splits(splits)
    return splits


def stratified_random_cascade_split(
    cascade_ids: list[str],
    labels: np.ndarray,
    *,
    train_ratio: float = 0.70,
    val_ratio: float = 0.10,
    seed: int = 42,
) -> SplitIndices:
    """Stratified random split by cascade_id for optimistic comparison only."""
    n = len(cascade_ids)
    if n < 5 or len(np.unique(labels)) < 2:
        # Deterministic fallback if too small or single-class
        rng = np.random.default_rng(seed)
        perm = rng.permutation(n)
        t_end = max(1, int(round(n * train_ratio)))
        v_end = max(t_end + 1, int(round(n * (train_ratio + val_ratio))))
        v_end = min(v_end, n - 1)
        t_end = min(t_end, v_end - 1)
        splits = SplitIndices(
            train_ids=[cascade_ids[i] for i in perm[:t_end]],
            val_ids=[cascade_ids[i] for i in perm[t_end:v_end]],
            test_ids=[cascade_ids[i] for i in perm[v_end:]],
        )
        assert_disjoint_splits(splits)
        return splits

    ids_arr = np.asarray(cascade_ids)
    test_size = max(0.05, 1.0 - train_ratio)
    try:
        sss1 = StratifiedShuffleSplit(n_splits=1, test_size=test_size, random_state=seed)
        train_idx, rest_idx = next(sss1.split(ids_arr, labels))

        rest_labels = labels[rest_idx]
        val_frac_of_rest = val_ratio / max(1.0 - train_ratio, 1e-6)
        if len(np.unique(rest_labels)) >= 2 and len(rest_idx) >= 4:
            sss2 = StratifiedShuffleSplit(
                n_splits=1, test_size=1.0 - val_frac_of_rest, random_state=seed
            )
            val_rel, test_rel = next(sss2.split(ids_arr[rest_idx], rest_labels))
            val_idx = rest_idx[val_rel]
            test_idx = rest_idx[test_rel]
        else:
            split_pt = max(1, int(round(len(rest_idx) * val_frac_of_rest)))
            val_idx = rest_idx[:split_pt]
            test_idx = rest_idx[split_pt:]
    except ValueError:
        rng = np.random.default_rng(seed)
        perm = rng.permutation(n)
        t_end = max(1, int(round(n * train_ratio)))
        v_end = max(t_end + 1, int(round(n * (train_ratio + val_ratio))))
        v_end = min(v_end, n - 1)
        train_idx, val_idx, test_idx = perm[:t_end], perm[t_end:v_end], perm[v_end:]

    splits = SplitIndices(
        train_ids=ids_arr[train_idx].tolist(),
        val_ids=ids_arr[val_idx].tolist(),
        test_ids=ids_arr[test_idx].tolist(),
    )
    assert_disjoint_splits(splits)
    return splits
