"""Hand-computed feature verification tests on chain of 4, star of 5, binary tree of 7."""

from __future__ import annotations

import math

import pandas as pd
import pytest

from app.services.features import FEATURE_NAMES, extract_cascade_features
from tests.fixtures import binary_tree_of_7_df, chain_of_4_df, star_of_5_df


def test_chain_of_4_exact_features() -> None:
    feats = extract_cascade_features(chain_of_4_df(), window_seconds=100.0)
    assert set(feats.keys()) == set(FEATURE_NAMES)
    assert feats["num_nodes"] == 4.0
    assert feats["num_edges"] == 3.0
    assert feats["max_degree"] == 2.0
    assert feats["avg_degree"] == pytest.approx(1.5)
    assert feats["degree_variance"] == pytest.approx(0.25)
    assert feats["max_depth"] == 3.0
    assert feats["avg_depth"] == pytest.approx(1.5)
    assert feats["max_branching"] == 1.0
    assert feats["avg_branching"] == pytest.approx(1.0)
    assert feats["density"] == pytest.approx(0.25)
    assert feats["clustering_coefficient"] == pytest.approx(0.0)
    assert feats["num_leaves"] == 1.0
    assert feats["leaf_ratio"] == pytest.approx(0.25)
    assert feats["num_components"] == 1.0
    assert feats["structural_virality"] == pytest.approx(5.0 / 3.0)
    assert feats["event_rate"] == pytest.approx(3.0 / 60.0)
    assert feats["time_to_third_event"] == pytest.approx(60.0)
    assert feats["median_inter_event_gap"] == pytest.approx(20.0)


def test_star_of_5_exact_features() -> None:
    feats = extract_cascade_features(star_of_5_df(), window_seconds=100.0)
    assert feats["num_nodes"] == 5.0
    assert feats["num_edges"] == 4.0
    assert feats["max_degree"] == 4.0
    assert feats["avg_degree"] == pytest.approx(1.6)
    assert feats["degree_variance"] == pytest.approx(1.44)
    assert feats["max_depth"] == 1.0
    assert feats["avg_depth"] == pytest.approx(0.8)
    assert feats["max_branching"] == 4.0
    assert feats["avg_branching"] == pytest.approx(4.0)
    assert feats["density"] == pytest.approx(0.2)
    assert feats["clustering_coefficient"] == pytest.approx(0.0)
    assert feats["num_leaves"] == 4.0
    assert feats["leaf_ratio"] == pytest.approx(0.8)
    assert feats["num_components"] == 1.0
    assert feats["structural_virality"] == pytest.approx(1.6)
    assert feats["event_rate"] == pytest.approx(4.0 / 50.0)
    assert feats["time_to_third_event"] == pytest.approx(30.0)
    assert feats["median_inter_event_gap"] == pytest.approx(12.5)


def test_binary_tree_of_7_exact_features() -> None:
    feats = extract_cascade_features(binary_tree_of_7_df(), window_seconds=200.0)
    assert feats["num_nodes"] == 7.0
    assert feats["num_edges"] == 6.0
    assert feats["max_degree"] == 3.0
    assert feats["avg_degree"] == pytest.approx(12.0 / 7.0)
    assert feats["degree_variance"] == pytest.approx(38.0 / 49.0)
    assert feats["max_depth"] == 2.0
    assert feats["avg_depth"] == pytest.approx(10.0 / 7.0)
    assert feats["max_branching"] == 2.0
    assert feats["avg_branching"] == pytest.approx(2.0)
    assert feats["density"] == pytest.approx(1.0 / 7.0)
    assert feats["clustering_coefficient"] == pytest.approx(0.0)
    assert feats["num_leaves"] == 4.0
    assert feats["leaf_ratio"] == pytest.approx(4.0 / 7.0)
    assert feats["num_components"] == 1.0
    assert feats["structural_virality"] == pytest.approx(16.0 / 7.0)
    assert feats["event_rate"] == pytest.approx(6.0 / 100.0)
    assert feats["time_to_third_event"] == pytest.approx(40.0)
    assert feats["median_inter_event_gap"] == pytest.approx(20.0)


def test_early_window_truncation_invariance() -> None:
    """Events strictly after T must never affect extracted features."""
    base = binary_tree_of_7_df()
    extra = pd.DataFrame(
        [
            {"cascade_id": "bin7", "parent_id": "n3", "child_id": "n7", "timestamp": 65.0},
            {"cascade_id": "bin7", "parent_id": "n6", "child_id": "n8", "timestamp": 500.0},
        ]
    )
    extended = pd.concat([base, extra], ignore_index=True)

    feats_base = extract_cascade_features(base, window_seconds=60.0)
    feats_ext = extract_cascade_features(extended, window_seconds=60.0)

    for name in FEATURE_NAMES:
        v1 = feats_base[name]
        v2 = feats_ext[name]
        if math.isnan(v1):
            assert math.isnan(v2)
        else:
            assert v1 == pytest.approx(v2)
