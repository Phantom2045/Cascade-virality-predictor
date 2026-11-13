"""Tiny graph fixtures allowed strictly for unit tests (chain of 4, star of 5, binary tree of 7)."""

from __future__ import annotations

import pandas as pd


def chain_of_4_df(cascade_id: str = "chain4") -> pd.DataFrame:
    """Directed chain n0 -> n1 -> n2 -> n3."""
    return pd.DataFrame(
        [
            {"cascade_id": cascade_id, "parent_id": None, "child_id": "n0", "timestamp": 0.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n1", "timestamp": 10.0},
            {"cascade_id": cascade_id, "parent_id": "n1", "child_id": "n2", "timestamp": 30.0},
            {"cascade_id": cascade_id, "parent_id": "n2", "child_id": "n3", "timestamp": 60.0},
        ]
    )


def star_of_5_df(cascade_id: str = "star5") -> pd.DataFrame:
    """Directed star with hub n0 and 4 leaves n1..n4."""
    return pd.DataFrame(
        [
            {"cascade_id": cascade_id, "parent_id": None, "child_id": "n0", "timestamp": 0.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n1", "timestamp": 5.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n2", "timestamp": 15.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n3", "timestamp": 30.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n4", "timestamp": 50.0},
        ]
    )


def binary_tree_of_7_df(cascade_id: str = "bin7") -> pd.DataFrame:
    """Complete binary tree of depth 2 (7 nodes, 6 edges)."""
    return pd.DataFrame(
        [
            {"cascade_id": cascade_id, "parent_id": None, "child_id": "n0", "timestamp": 0.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n1", "timestamp": 10.0},
            {"cascade_id": cascade_id, "parent_id": "n0", "child_id": "n2", "timestamp": 20.0},
            {"cascade_id": cascade_id, "parent_id": "n1", "child_id": "n3", "timestamp": 40.0},
            {"cascade_id": cascade_id, "parent_id": "n1", "child_id": "n4", "timestamp": 60.0},
            {"cascade_id": cascade_id, "parent_id": "n2", "child_id": "n5", "timestamp": 80.0},
            {"cascade_id": cascade_id, "parent_id": "n2", "child_id": "n6", "timestamp": 100.0},
        ]
    )
