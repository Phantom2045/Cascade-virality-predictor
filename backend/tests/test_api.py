"""API endpoint integration tests using FastAPI TestClient."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from app.ml.datasets.canonical_csv import CanonicalCsvAdapter
from app.ml.train import run_training_pipeline
from tests.test_training import _write_fixture_corpus


def _make_empty_client(tmp_path: Path) -> TestClient:
    settings = Settings(
        backend_root=tmp_path / "empty_backend",
        early_window_seconds=120.0,
        max_upload_bytes=1024,
    )
    app = create_app(settings)
    return TestClient(app)


def _make_trained_client(tmp_path: Path) -> TestClient:
    backend_root = tmp_path / "trained_backend"
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
        max_upload_bytes=50_000,
    )
    bundle = CanonicalCsvAdapter("fixture_corpus").load(raw_dir)
    run_training_pipeline(
        bundle, settings, window_seconds=120.0, virality_quantile=0.80, tune_rf=False
    )
    app = create_app(settings)
    return TestClient(app)


def test_empty_state_returns_structured_errors(tmp_path: Path) -> None:
    with _make_empty_client(tmp_path) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.json()["model_loaded"] is False
        assert health.json()["dataset_loaded"] is False

        info = client.get("/api/model/info")
        assert info.status_code == 503
        assert info.json()["code"] == "MODEL_NOT_TRAINED"

        cascades = client.get("/api/cascades")
        assert cascades.status_code == 404
        assert cascades.json()["code"] == "NO_DATASET"

        report = client.get("/api/report")
        assert report.status_code == 503
        assert report.json()["code"] == "MODEL_NOT_TRAINED"


def test_trained_endpoints_flow(tmp_path: Path) -> None:
    with _make_trained_client(tmp_path) as client:
        assert client.get("/api/health").json()["model_loaded"] is True

        info = client.get("/api/model/info")
        assert info.status_code == 200
        assert info.json()["dataset_name"] == "fixture_corpus"

        cascades = client.get("/api/cascades?limit=5&offset=0")
        assert cascades.status_code == 200
        data = cascades.json()
        assert data["total"] == 20
        first_id = data["items"][0]["cascade_id"]

        tree = client.get(f"/api/cascades/{first_id}")
        assert tree.status_code == 200
        assert tree.json()["cascade_id"] == first_id
        assert len(tree.json()["nodes"]) >= 4

        pred_id = client.post("/api/predict", json={"cascade_id": first_id})
        assert pred_id.status_code == 200
        p = pred_id.json()["predictions"][0]
        assert p["excluded"] is False
        assert 0.0 <= p["virality_probability"] <= 1.0
        assert len(p["top_factors"]) > 0

        report = client.get("/api/report")
        assert report.status_code == 200
        assert len(report.json()["temporal_test_results"]) == 4


def test_upload_validation_predict_excluded_and_oversized(tmp_path: Path) -> None:
    with _make_trained_client(tmp_path) as client:
        # Bad CSV missing column
        bad = client.post(
            "/api/validate",
            files={"file": ("bad.csv", b"cascade_id,parent_id,timestamp\nc1,,0\n", "text/csv")},
        )
        assert bad.status_code == 400
        assert bad.json()["code"] == "INVALID_INPUT"

        # Excluded cascade (< 3 early edges)
        small_csv = (
            b"cascade_id,parent_id,child_id,timestamp\n"
            b"tiny,,u0,0\n"
            b"tiny,u0,u1,5\n"
            b"tiny,u1,u2,10\n"
        )
        pred_small = client.post(
            "/api/predict",
            files={"file": ("tiny.csv", small_csv, "text/csv")},
        )
        assert pred_small.status_code == 200
        res = pred_small.json()["predictions"][0]
        assert res["excluded"] is True
        assert "minimum 3 required" in res["exclusion_reason"]

        # Oversized CSV
        big_bytes = b"cascade_id,parent_id,child_id,timestamp\n" + (b"c1,a,b,1\n" * 10_000)
        too_big = client.post(
            "/api/validate",
            files={"file": ("big.csv", big_bytes, "text/csv")},
        )
        assert too_big.status_code == 413
        assert too_big.json()["code"] == "PAYLOAD_TOO_LARGE"
