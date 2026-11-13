"""Adapter for real datasets exported as a canonical CSV file (`edges.csv`)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from app.errors import NoDatasetError
from app.ml.datasets.base import (
    DatasetBundle,
    compute_cascade_metadata,
    compute_files_sha256,
)
from app.services.validation import parse_canonical_csv, validate_and_clean_edges


class CanonicalCsvAdapter:
    """Load a user-supplied real dataset stored in canonical CSV format.

    Expected path: `<raw_dir>/<name>/edges.csv` (and optional `metadata.csv` with
    `cascade_id,root_timestamp,observation_horizon_seconds`).
    """

    def __init__(self, name: str = "canonical") -> None:
        self.name = name
        self.source_description = (
            f"User-provided real propagation dataset '{name}' in canonical edge-list CSV format."
        )
        self.reconstruction_note = (
            "Parent-child relationships and relative timestamps come directly from "
            "the supplied edges.csv."
        )

    def _edges_path(self, raw_dir: Path) -> Path:
        return raw_dir / self.name / "edges.csv"

    def is_available(self, raw_dir: Path) -> bool:
        return self._edges_path(raw_dir).is_file()

    def load(self, raw_dir: Path) -> DatasetBundle:
        edges_path = self._edges_path(raw_dir)
        if not edges_path.is_file():
            raise NoDatasetError(
                f"Dataset '{self.name}' not found at '{edges_path}'.",
                details={"expected_path": str(edges_path)},
            )

        raw_df = parse_canonical_csv(edges_path.read_bytes())
        cleaned_edges, validation_report = validate_and_clean_edges(raw_df)

        meta_path = edges_path.parent / "metadata.csv"
        root_timestamps: dict[str, float] = {}
        horizon: float | None = None
        files_to_hash = [edges_path]

        if meta_path.is_file():
            files_to_hash.append(meta_path)
            meta_df = pd.read_csv(meta_path, dtype={"cascade_id": str})
            if "cascade_id" in meta_df.columns and "root_timestamp" in meta_df.columns:
                for row in meta_df.itertuples(index=False):
                    root_timestamps[str(row.cascade_id)] = float(row.root_timestamp)
            if "observation_horizon_seconds" in meta_df.columns and not meta_df.empty:
                horizon = float(meta_df["observation_horizon_seconds"].max())
        else:
            # Deterministic ordering when no external root timestamp metadata is given
            cascade_ids = cleaned_edges["cascade_id"].astype(str).unique().tolist()
            for idx, cid in enumerate(cascade_ids):
                root_timestamps[cid] = float(idx)

        metadata = compute_cascade_metadata(
            cleaned_edges,
            root_timestamps,
            observation_horizon_seconds=horizon,
        )
        resolved_horizon = (
            float(metadata["observation_horizon_seconds"].max())
            if not metadata.empty
            else 0.0
        )

        return DatasetBundle(
            dataset_name=self.name,
            dataset_hash=compute_files_sha256(files_to_hash),
            source_description=self.source_description,
            reconstruction_note=self.reconstruction_note,
            observation_horizon_seconds=resolved_horizon,
            edges_df=cleaned_edges,
            cascade_metadata=metadata,
            validation_report=validation_report,
        )
