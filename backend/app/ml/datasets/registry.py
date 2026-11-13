"""Dataset adapter registry and discovery."""

from __future__ import annotations

import contextlib
from pathlib import Path

from app.errors import NoDatasetError
from app.ml.datasets.base import DatasetAdapter
from app.ml.datasets.canonical_csv import CanonicalCsvAdapter
from app.ml.datasets.pheme import PhemeAdapter
from app.ml.datasets.twitter15_16 import Twitter1516Adapter


def get_adapter(dataset_name: str, raw_dir: Path | None = None) -> DatasetAdapter:
    """Resolve a dataset adapter by name, supporting built-in and canonical folders."""
    normalized = dataset_name.strip().lower()
    if normalized in {"twitter15", "twitter16"}:
        return Twitter1516Adapter(variant=normalized)
    if normalized == "pheme":
        return PhemeAdapter()
    if raw_dir is not None and (raw_dir / dataset_name / "edges.csv").is_file():
        return CanonicalCsvAdapter(name=dataset_name)
    if normalized == "canonical":
        return CanonicalCsvAdapter(name="canonical")
    raise NoDatasetError(
        f"Unknown or unconfigured dataset '{dataset_name}'. "
        "Supported adapters: twitter15, twitter16, pheme, or <name>/edges.csv.",
        details={"requested_dataset": dataset_name},
    )


def discover_available_dataset(
    raw_dir: Path, preferred: str | None = None
) -> DatasetAdapter | None:
    """Find the preferred or first available real dataset under raw_dir, or return None."""
    if not raw_dir.is_dir():
        return None

    candidates: list[DatasetAdapter] = []
    if preferred:
        with contextlib.suppress(NoDatasetError):
            candidates.append(get_adapter(preferred, raw_dir))

    for name in ("twitter15", "twitter16", "pheme"):
        if name != preferred:
            candidates.append(get_adapter(name, raw_dir))

    for sub in sorted(raw_dir.iterdir()):
        if sub.is_dir() and (sub / "edges.csv").is_file():
            candidates.append(CanonicalCsvAdapter(name=sub.name))

    for adapter in candidates:
        if adapter.is_available(raw_dir):
            return adapter
    return None
