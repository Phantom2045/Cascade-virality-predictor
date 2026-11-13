"""DatasetAdapter protocol and canonical DatasetBundle contract."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd

from app.schemas import ValidationReport


@dataclass(frozen=True)
class DatasetBundle:
    """Canonical edges, cascade metadata, and provenance returned by a real dataset adapter."""

    dataset_name: str
    dataset_hash: str
    source_description: str
    reconstruction_note: str
    observation_horizon_seconds: float
    edges_df: pd.DataFrame
    cascade_metadata: pd.DataFrame
    validation_report: ValidationReport


class DatasetAdapter(Protocol):
    """Protocol that every real-data adapter must implement."""

    name: str
    source_description: str
    reconstruction_note: str

    def is_available(self, raw_dir: Path) -> bool:
        """Return True if the raw dataset files exist under raw_dir."""
        ...

    def load(self, raw_dir: Path) -> DatasetBundle:
        """Load raw files, convert to canonical edge list, validate, and build metadata."""
        ...


def compute_files_sha256(paths: list[Path]) -> str:
    """Compute a deterministic SHA-256 fingerprint across dataset files."""
    hasher = hashlib.sha256()
    for p in sorted(paths):
        hasher.update(p.name.encode("utf-8"))
        with p.open("rb") as fh:
            while chunk := fh.read(65536):
                hasher.update(chunk)
    return hasher.hexdigest()[:16]


def compute_cascade_metadata(
    cleaned_edges: pd.DataFrame,
    root_timestamps: dict[str, float],
    observation_horizon_seconds: float | None = None,
) -> pd.DataFrame:
    """Compute per-cascade final distinct node count, root timestamp, and horizon."""
    rows: list[dict[str, str | int | float]] = []
    max_observed = (
        float(cleaned_edges["timestamp"].max()) if not cleaned_edges.empty else 0.0
    )
    horizon = (
        float(observation_horizon_seconds)
        if observation_horizon_seconds is not None
        else max_observed
    )

    for cid, grp in cleaned_edges.groupby("cascade_id", sort=False):
        cid_str = str(cid)
        nodes = set(grp["child_id"].astype(str))
        parent_series = grp.loc[grp["parent_id"].notna(), "parent_id"].astype(str)
        nodes.update(parent_series.tolist())
        rows.append(
            {
                "cascade_id": cid_str,
                "root_timestamp": float(root_timestamps.get(cid_str, 0.0)),
                "final_size": int(len(nodes)),
                "observation_horizon_seconds": float(horizon),
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["cascade_id", "root_timestamp", "final_size", "observation_horizon_seconds"]
        )
    return pd.DataFrame(rows).sort_values(
        by=["root_timestamp", "cascade_id"], kind="mergesort"
    ).reset_index(drop=True)
