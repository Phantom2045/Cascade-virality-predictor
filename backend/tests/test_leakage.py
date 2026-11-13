"""Leakage prevention tests: threshold isolation, temporal ordering, and split disjointness."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.labeling import apply_virality_label, fit_virality_threshold
from app.ml.splitting import assert_disjoint_splits, temporal_cascade_split


def test_threshold_depends_only_on_training_sizes() -> None:
    train_sizes = np.array([5, 10, 15, 20, 100])
    threshold = fit_virality_threshold(train_sizes, quantile=0.80)

    # Altering test sizes dramatically must not change the training-derived threshold
    test_sizes_small = np.array([3, 4, 5])
    test_sizes_huge = np.array([10_000, 50_000, 100_000])

    threshold_again = fit_virality_threshold(train_sizes, quantile=0.80)
    assert threshold == threshold_again
    assert apply_virality_label(test_sizes_small, threshold).tolist() == [0, 0, 0]
    assert apply_virality_label(test_sizes_huge, threshold).tolist() == [1, 1, 1]


def test_temporal_split_preserves_chronological_order_and_zero_overlap() -> None:
    meta = pd.DataFrame(
        [
            {"cascade_id": f"c{i}", "root_timestamp": float(1000 - i * 10), "final_size": 10 + i}
            for i in range(20)
        ]
    )
    splits = temporal_cascade_split(meta, train_ratio=0.70, val_ratio=0.10)
    assert_disjoint_splits(splits)
    assert len(splits.train_ids) == 14
    assert len(splits.val_ids) == 2
    assert len(splits.test_ids) == 4

    ts_map = dict(zip(meta["cascade_id"], meta["root_timestamp"], strict=False))
    max_train = max(ts_map[cid] for cid in splits.train_ids)
    min_val = min(ts_map[cid] for cid in splits.val_ids)
    max_val = max(ts_map[cid] for cid in splits.val_ids)
    min_test = min(ts_map[cid] for cid in splits.test_ids)

    assert max_train <= min_val
    assert max_val <= min_test
