"""Tests for canonical CSV parsing and explicit validation/cleaning."""

from __future__ import annotations

import pandas as pd
import pytest

from app.errors import InvalidInputError
from app.services.validation import parse_canonical_csv, validate_and_clean_edges


def test_parse_canonical_csv_missing_columns() -> None:
    raw = b"cascade_id,parent_id,timestamp\nc1,,0\n"
    with pytest.raises(InvalidInputError) as exc_info:
        parse_canonical_csv(raw)
    assert "child_id" in str(exc_info.value.details)


def test_parse_canonical_csv_empty() -> None:
    with pytest.raises(InvalidInputError):
        parse_canonical_csv(b"   ")


def test_validation_detects_and_reports_all_issue_types() -> None:
    df = pd.DataFrame(
        [
            # Valid root + edge
            {"cascade_id": "c1", "parent_id": None, "child_id": "u0", "timestamp": 0.0},
            {"cascade_id": "c1", "parent_id": "u0", "child_id": "u1", "timestamp": 5.0},
            # Exact duplicate edge (later timestamp)
            {"cascade_id": "c1", "parent_id": "u0", "child_id": "u1", "timestamp": 12.0},
            # Multiple parent conflict for u2 -> earliest (u1 at 10.0) survives
            {"cascade_id": "c1", "parent_id": "u0", "child_id": "u2", "timestamp": 20.0},
            {"cascade_id": "c1", "parent_id": "u1", "child_id": "u2", "timestamp": 10.0},
            # Self-loop
            {"cascade_id": "c1", "parent_id": "u1", "child_id": "u1", "timestamp": 15.0},
            # Negative timestamp
            {"cascade_id": "c1", "parent_id": "u1", "child_id": "u3", "timestamp": -3.0},
            # Malformed timestamp
            {"cascade_id": "c1", "parent_id": "u1", "child_id": "u4", "timestamp": "bad"},
            # Directed cycle in c2: a -> b (10.0) and b -> a (25.0)
            {"cascade_id": "c2", "parent_id": "a", "child_id": "b", "timestamp": 10.0},
            {"cascade_id": "c2", "parent_id": "b", "child_id": "a", "timestamp": 25.0},
            # Multiple roots in c3 (r1 -> x1, r2 -> x2)
            {"cascade_id": "c3", "parent_id": None, "child_id": "r1", "timestamp": 0.0},
            {"cascade_id": "c3", "parent_id": "r1", "child_id": "x1", "timestamp": 5.0},
            {"cascade_id": "c3", "parent_id": None, "child_id": "r2", "timestamp": 1.0},
            {"cascade_id": "c3", "parent_id": "r2", "child_id": "x2", "timestamp": 6.0},
        ]
    )

    cleaned, report = validate_and_clean_edges(df)

    assert report.is_valid is True
    assert report.total_rows == 14
    assert report.malformed_rows_dropped == 1
    assert report.negative_timestamps_dropped == 1
    assert report.self_loops_dropped == 1
    assert report.duplicate_edges_dropped == 1
    assert report.multiple_parents_resolved == 1
    assert report.cycles_detected == 1
    assert report.cycle_edges_removed == 1
    assert report.multiple_roots_cascades == 1
    assert len(report.actions_taken) >= 6
    assert len(report.warnings) == 1

    # Verify earliest parent survived for u2
    c1_u2 = cleaned[(cleaned["cascade_id"] == "c1") & (cleaned["child_id"] == "u2")]
    assert len(c1_u2) == 1
    assert c1_u2.iloc[0]["parent_id"] == "u1"
    assert float(c1_u2.iloc[0]["timestamp"]) == 10.0

    # Verify latest edge (b -> a at 25.0) was removed to break cycle in c2
    c2_edges = cleaned[cleaned["cascade_id"] == "c2"]
    assert len(c2_edges) == 1
    assert c2_edges.iloc[0]["parent_id"] == "a"
    assert c2_edges.iloc[0]["child_id"] == "b"
