"""Tests for propagation graph construction, forest handling, and window truncation."""

from __future__ import annotations

import pandas as pd
import pytest

from app.errors import FutureEventLeakageError
from app.services.graph import (
    assert_no_future_events,
    build_cascade_graph,
    serialize_tree_for_api,
    truncate_to_window,
)
from tests.fixtures import binary_tree_of_7_df, chain_of_4_df, star_of_5_df


def test_build_graph_direction_roots_leaves_depth_on_fixtures() -> None:
    chain_info = build_cascade_graph(chain_of_4_df())
    assert chain_info.roots == ["n0"]
    assert chain_info.leaves == ["n3"]
    assert chain_info.depths == {"n0": 0, "n1": 1, "n2": 2, "n3": 3}

    star_info = build_cascade_graph(star_of_5_df())
    assert star_info.roots == ["n0"]
    assert star_info.leaves == ["n1", "n2", "n3", "n4"]
    assert star_info.depths == {"n0": 0, "n1": 1, "n2": 1, "n3": 1, "n4": 1}

    bin_info = build_cascade_graph(binary_tree_of_7_df())
    assert bin_info.roots == ["n0"]
    assert bin_info.leaves == ["n3", "n4", "n5", "n6"]
    assert bin_info.depths == {"n0": 0, "n1": 1, "n2": 1, "n3": 2, "n4": 2, "n5": 2, "n6": 2}


def test_forest_handling_multiple_roots() -> None:
    forest_df = pd.DataFrame(
        [
            {"cascade_id": "f1", "parent_id": None, "child_id": "r1", "timestamp": 0.0},
            {"cascade_id": "f1", "parent_id": "r1", "child_id": "a", "timestamp": 5.0},
            {"cascade_id": "f1", "parent_id": None, "child_id": "r2", "timestamp": 10.0},
            {"cascade_id": "f1", "parent_id": "r2", "child_id": "b", "timestamp": 15.0},
        ]
    )
    info = build_cascade_graph(forest_df)
    assert info.roots == ["r1", "r2"]
    assert info.depths["r1"] == 0
    assert info.depths["r2"] == 0
    assert info.depths["a"] == 1
    assert info.depths["b"] == 1


def test_truncate_to_window_and_leakage_guard() -> None:
    df = binary_tree_of_7_df()
    truncated = truncate_to_window(df, window_seconds=40.0)
    assert float(truncated["timestamp"].max()) <= 40.0
    assert len(truncated) == 4  # n0 (0), n1 (10), n2 (20), n3 (40)

    with pytest.raises(FutureEventLeakageError):
        assert_no_future_events(df, max_timestamp=40.0)


def test_serialize_tree_caps_large_cascade() -> None:
    rows = [{"cascade_id": "big", "parent_id": None, "child_id": "n0", "timestamp": 0.0}]
    for i in range(1, 20):
        rows.append(
            {
                "cascade_id": "big",
                "parent_id": "n0",
                "child_id": f"n{i}",
                "timestamp": float(i),
            }
        )
    df = pd.DataFrame(rows)
    res = serialize_tree_for_api(
        cascade_id="big",
        cascade_df=df,
        window_seconds=100.0,
        stats={"num_nodes": 20.0},
        max_nodes=10,
    )
    assert res.truncated is True
    assert res.total_nodes == 20
    assert res.returned_nodes == 10
    assert res.truncation_notice is not None
