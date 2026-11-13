"""Startup cache and loader for trained model artifacts, metrics, and real datasets."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import joblib
import pandas as pd

from app.config import Settings
from app.errors import CascadeNotFoundError, ModelNotTrainedError, NoDatasetError
from app.ml.datasets.base import DatasetBundle
from app.ml.datasets.registry import discover_available_dataset, get_adapter
from app.schemas import ReportResponse

logger = logging.getLogger(__name__)


@dataclass
class LoadedModelArtifact:
    """Loaded joblib pipeline alongside its .meta.json provenance."""

    pipeline: Any
    meta: dict[str, Any]
    model_path: Path
    meta_path: Path


@dataclass
class AppStore:
    """In-memory cache populated at FastAPI startup without synthetic fallbacks."""

    settings: Settings
    model: LoadedModelArtifact | None = None
    dataset: DatasetBundle | None = None
    report: ReportResponse | None = None
    _edges_by_cascade: dict[str, pd.DataFrame] = field(default_factory=dict)

    def reload(self) -> None:
        self.model = self._load_model()
        preferred = (
            self.model.meta.get("dataset_name")
            if self.model is not None
            else self.settings.active_dataset
        )
        self.dataset = self._load_dataset(str(preferred))
        self._edges_by_cascade = {}
        if self.dataset is not None and not self.dataset.edges_df.empty:
            for cid, grp in self.dataset.edges_df.groupby("cascade_id", sort=False):
                self._edges_by_cascade[str(cid)] = grp
        self.report = self._load_report()

    def _load_model(self) -> LoadedModelArtifact | None:
        models_dir = self.settings.models_dir
        if not models_dir.is_dir():
            return None

        active_file = models_dir / "active_model.json"
        model_path: Path | None = None
        meta_path: Path | None = None

        if active_file.is_file():
            try:
                pointer = json.loads(active_file.read_text(encoding="utf-8"))
                cand_m = models_dir / str(pointer.get("model_file", ""))
                cand_meta = models_dir / str(pointer.get("meta_file", ""))
                if cand_m.is_file() and cand_meta.is_file():
                    model_path, meta_path = cand_m, cand_meta
            except Exception as exc:
                logger.warning("Failed to parse active_model.json: %s", exc)

        if model_path is None or meta_path is None:
            meta_files = sorted(models_dir.glob("*_rf.meta.json"))
            if meta_files:
                meta_path = meta_files[0]
                stem = meta_path.name.removesuffix(".meta.json")
                cand = models_dir / f"{stem}.joblib"
                if cand.is_file():
                    model_path = cand

        if model_path is None or meta_path is None:
            return None

        pipeline = joblib.load(model_path)
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        return LoadedModelArtifact(
            pipeline=pipeline,
            meta=meta,
            model_path=model_path,
            meta_path=meta_path,
        )

    def _load_dataset(self, preferred: str) -> DatasetBundle | None:
        raw_dir = self.settings.data_raw_dir
        adapter = discover_available_dataset(raw_dir, preferred=preferred)
        if adapter is None:
            return None
        try:
            return adapter.load(raw_dir)
        except NoDatasetError:
            return None

    def _load_report(self) -> ReportResponse | None:
        metrics_path = self.settings.metrics_path
        if not metrics_path.is_file():
            return None
        raw = json.loads(metrics_path.read_text(encoding="utf-8"))
        return ReportResponse.model_validate(raw)

    def require_model(self) -> LoadedModelArtifact:
        if self.model is None:
            raise ModelNotTrainedError(
                "No trained model found. Place a real dataset under backend/data/raw/ and run "
                "`python -m app.ml.train --dataset <name>`."
            )
        return self.model

    def require_dataset(self) -> DatasetBundle:
        if self.dataset is None:
            raise NoDatasetError(
                "No real dataset found under backend/data/raw/. "
                "See README.md or docs/data-sources.md for dataset setup instructions."
            )
        return self.dataset

    def require_report(self) -> ReportResponse:
        if self.report is None:
            raise ModelNotTrainedError(
                "No evaluation report found at backend/reports/metrics.json. "
                "Train a model first using `python -m app.ml.train --dataset <name>`."
            )
        return self.report

    def get_cascade_edges(self, cascade_id: str) -> pd.DataFrame:
        self.require_dataset()
        grp = self._edges_by_cascade.get(cascade_id)
        if grp is None:
            raise CascadeNotFoundError(
                f"Cascade '{cascade_id}' was not found in the active dataset.",
                details={"cascade_id": cascade_id},
            )
        return grp

    def effective_window_seconds(self) -> float:
        if self.model is not None:
            return float(
                self.model.meta.get(
                    "early_window_seconds", self.settings.early_window_seconds
                )
            )
        return self.settings.early_window_seconds

    def effective_dataset_name(self) -> str | None:
        if self.dataset is not None:
            return self.dataset.dataset_name
        if self.model is not None:
            return str(self.model.meta.get("dataset_name"))
        return None


def try_load_specific_dataset(raw_dir: Path, name: str) -> DatasetBundle | None:
    try:
        adapter = get_adapter(name, raw_dir)
        return adapter.load(raw_dir)
    except NoDatasetError:
        return None
