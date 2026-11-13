"""Tests for dataset adapters and empty-data handling."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.errors import NoDatasetError
from app.ml.datasets.registry import discover_available_dataset, get_adapter


def test_missing_dataset_raises_no_dataset_error(tmp_path: Path) -> None:
    adapter = get_adapter("twitter15")
    assert adapter.is_available(tmp_path) is False
    with pytest.raises(NoDatasetError):
        adapter.load(tmp_path)
    assert discover_available_dataset(tmp_path, preferred="twitter15") is None


def test_twitter15_adapter_parses_tree_format_and_ignores_labels(tmp_path: Path) -> None:
    ds_dir = tmp_path / "twitter15"
    tree_dir = ds_dir / "tree"
    tree_dir.mkdir(parents=True)
    # Minimal Ma et al. formatted tree file (using Twitter Snowflake ID)
    (ds_dir / "label.txt").write_text("false:552783667052167168\n", encoding="utf-8")
    (tree_dir / "552783667052167168.txt").write_text(
        "['ROOT', 'ROOT', '0.0']->['u0', '552783667052167168', '0.0']\n"
        "['u0', '552783667052167168', '0.0']->['u1', '552784000000000001', '0.5']\n"
        "['u1', '552784000000000001', '0.5']->['u2', '552785000000000002', '2.0']\n"
        "['u0', '552783667052167168', '0.0']->['u3', '552786000000000003', '3.0']\n",
        encoding="utf-8",
    )

    adapter = get_adapter("twitter15")
    assert adapter.is_available(tmp_path) is True
    bundle = adapter.load(tmp_path)

    assert bundle.dataset_name == "twitter15"
    assert len(bundle.cascade_metadata) == 1
    assert int(bundle.cascade_metadata.iloc[0]["final_size"]) == 4
    assert bundle.edges_df["timestamp"].max() == pytest.approx(180.0)


def test_pheme_adapter_parses_structure_and_timestamps(tmp_path: Path) -> None:
    thread = tmp_path / "pheme" / "event1" / "rumours" / "100"
    (thread / "source-tweet").mkdir(parents=True)
    (thread / "reactions").mkdir(parents=True)

    (thread / "source-tweet" / "100.json").write_text(
        json.dumps({"id_str": "100", "created_at": "Wed Jan 07 11:00:00 +0000 2015"}),
        encoding="utf-8",
    )
    (thread / "reactions" / "101.json").write_text(
        json.dumps({"id_str": "101", "created_at": "Wed Jan 07 11:01:00 +0000 2015"}),
        encoding="utf-8",
    )
    (thread / "reactions" / "102.json").write_text(
        json.dumps({"id_str": "102", "created_at": "Wed Jan 07 11:03:00 +0000 2015"}),
        encoding="utf-8",
    )
    (thread / "structure.json").write_text(
        json.dumps({"100": {"101": {"102": {}}}}),
        encoding="utf-8",
    )

    adapter = get_adapter("pheme")
    bundle = adapter.load(tmp_path)
    assert len(bundle.cascade_metadata) == 1
    assert int(bundle.cascade_metadata.iloc[0]["final_size"]) == 3
    assert sorted(bundle.edges_df["timestamp"].tolist()) == [0.0, 60.0, 180.0]
