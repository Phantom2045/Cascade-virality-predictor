"""End-to-end training and artifact reload verification on fixture-built canonical frames."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import pandas as pd

from app.config import Settings
from app.ml.datasets.canonical_csv import CanonicalCsvAdapter
from app.ml.train import run_training_pipeline
from app.services.features import FEATURE_NAMES, extract_features_table


def _write_fixture_corpus(raw_dir: Path) -> None:
    """Assemble a minimal corpus strictly from the 3 allowed fixture topologies."""
    ds_dir = raw_dir / "fixture_corpus"
    ds_dir.mkdir(parents=True)

    rows: list[dict[str, object]] = []
    meta_rows: list[dict[str, object]] = []

    # 15 small cascades (chain of 4 / star of 5) and 5 larger cascades (binary tree of 7 + late)
    for i in range(20):
        cid = f"c_{i:02d}"
        meta_rows.append(
            {
                "cascade_id": cid,
                "root_timestamp": float(1_700_000_000 + i * 3600),
                "observation_horizon_seconds": 500.0,
            }
        )
        if i % 4 == 3:
            # Larger cascade (binary tree of 7 inside early window + 2 late nodes)
            edges = [
                (None, "n0", 0.0),
                ("n0", "n1", 10.0),
                ("n0", "n2", 20.0),
                ("n1", "n3", 40.0),
                ("n1", "n4", 60.0),
                ("n2", "n5", 80.0),
                ("n2", "n6", 100.0),
                ("n3", "n7", 250.0),
                ("n4", "n8", 300.0),
            ]
        elif i % 2 == 0:
            # Chain of 4
            edges = [
                (None, "n0", 0.0),
                ("n0", "n1", 10.0),
                ("n1", "n2", 30.0),
                ("n2", "n3", 60.0),
            ]
        else:
            # Star of 5
            edges = [
                (None, "n0", 0.0),
                ("n0", "n1", 5.0),
                ("n0", "n2", 15.0),
                ("n0", "n3", 30.0),
                ("n0", "n4", 50.0),
            ]
        for p, ch, ts in edges:
            rows.append(
                {
                    "cascade_id": cid,
                    "parent_id": "" if p is None else p,
                    "child_id": ch,
                    "timestamp": ts,
                }
            )

    pd.DataFrame(rows).to_csv(ds_dir / "edges.csv", index=False)
    pd.DataFrame(meta_rows).to_csv(ds_dir / "metadata.csv", index=False)


def test_end_to_end_training_saves_and_reloads_identical_predictions(tmp_path: Path) -> None:
    backend_root = tmp_path / "backend"
    raw_dir = backend_root / "data" / "raw"
    _write_fixture_corpus(raw_dir)

    settings = Settings(
        seed=42,
        early_window_seconds=120.0,
        virality_quantile=0.80,
        sensitivity_quantiles=(0.80, 0.90),
        bootstrap_iterations=20,
        backend_root=backend_root,
        active_dataset="fixture_corpus",
    )

    bundle = CanonicalCsvAdapter("fixture_corpus").load(raw_dir)
    summary = run_training_pipeline(
        bundle, settings, window_seconds=120.0, virality_quantile=0.80, tune_rf=False
    )

    model_path = Path(summary["model_path"])
    meta_path = Path(summary["meta_path"])
    metrics_path = Path(summary["metrics_path"])

    assert model_path.is_file()
    assert meta_path.is_file()
    assert metrics_path.is_file()
    assert settings.curves_path.is_file()

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    assert meta["early_window_seconds"] == 120.0
    assert meta["feature_names"] == list(FEATURE_NAMES)

    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    assert len(metrics["temporal_test_results"]) == 4
    assert len(metrics["random_split_comparison"]) == 2
    assert len(metrics["threshold_sensitivity"]) == 2

    # Reload and verify identical predictions
    reloaded = joblib.load(model_path)
    feats = extract_features_table(bundle.edges_df, window_seconds=120.0)[list(FEATURE_NAMES)]
    probs_1 = reloaded.predict_proba(feats)[:, 1]
    reloaded_again = joblib.load(model_path)
    probs_2 = reloaded_again.predict_proba(feats)[:, 1]
    assert probs_1.tolist() == probs_2.tolist()
