"""Frozen application settings and path resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def _default_backend_root() -> Path:
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    """Immutable configuration for training, evaluation, and API serving."""

    seed: int = 42
    early_window_seconds: float = 3600.0
    virality_quantile: float = 0.80
    sensitivity_quantiles: tuple[float, ...] = (0.80, 0.90, 0.95)
    min_early_edges: int = 3
    max_upload_bytes: int = 10 * 1024 * 1024  # 10 MB
    max_tree_nodes_response: int = 1000
    wiener_exact_max_nodes: int = 500
    wiener_sample_sources: int = 128
    bootstrap_iterations: int = 500
    train_ratio: float = 0.70
    val_ratio: float = 0.10
    test_ratio: float = 0.20
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )
    active_dataset: str = "twitter15"
    backend_root: Path = _default_backend_root()

    @property
    def data_raw_dir(self) -> Path:
        env = os.environ.get("CVP_DATA_RAW_DIR")
        return Path(env) if env else self.backend_root / "data" / "raw"

    @property
    def data_processed_dir(self) -> Path:
        env = os.environ.get("CVP_DATA_PROCESSED_DIR")
        return Path(env) if env else self.backend_root / "data" / "processed"

    @property
    def models_dir(self) -> Path:
        env = os.environ.get("CVP_MODELS_DIR")
        return Path(env) if env else self.backend_root / "models"

    @property
    def reports_dir(self) -> Path:
        env = os.environ.get("CVP_REPORTS_DIR")
        return Path(env) if env else self.backend_root / "reports"

    @property
    def metrics_path(self) -> Path:
        return self.reports_dir / "metrics.json"

    @property
    def curves_path(self) -> Path:
        return self.reports_dir / "curves.json"


def get_settings() -> Settings:
    """Build settings with optional environment overrides."""
    root_env = os.environ.get("CVP_BACKEND_ROOT")
    backend_root = Path(root_env) if root_env else _default_backend_root()
    dataset = os.environ.get("CVP_DATASET", "twitter15")
    window_env = os.environ.get("CVP_EARLY_WINDOW_SECONDS")
    quantile_env = os.environ.get("CVP_VIRALITY_QUANTILE")
    return Settings(
        early_window_seconds=float(window_env) if window_env else 3600.0,
        virality_quantile=float(quantile_env) if quantile_env else 0.80,
        active_dataset=dataset,
        backend_root=backend_root,
    )
