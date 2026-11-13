"""Adapter for PHEME conversation-tree dataset (structure.json + tweet timestamps only)."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

from app.errors import NoDatasetError
from app.ml.datasets.base import (
    DatasetBundle,
    compute_cascade_metadata,
    compute_files_sha256,
)
from app.services.validation import validate_and_clean_edges


def _parse_twitter_created_at(created_at: str) -> float | None:
    if not created_at:
        return None
    for fmt in ("%a %b %d %H:%M:%S %z %Y", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(created_at, fmt).timestamp()
        except ValueError:
            continue
    return None


def _walk_structure(
    node: Any,
    parent_id: str | None,
    pairs: list[tuple[str | None, str]],
) -> None:
    if not isinstance(node, dict):
        return
    for child_id, subtree in node.items():
        cid = str(child_id).strip()
        pairs.append((parent_id, cid))
        _walk_structure(subtree, cid, pairs)


class PhemeAdapter:
    """Load PHEME Figshare conversation trees using structure.json and tweet timestamps only.

    Veracity labels (`annotation.json`) and tweet text are strictly ignored.
    """

    def __init__(self) -> None:
        self.name = "pheme"
        self.source_description = (
            "PHEME rumour conversation-tree dataset (structure.json reply links and tweet "
            "timestamps only; veracity annotations and text excluded)."
        )
        self.reconstruction_note = (
            "Uses observed reply-to conversation trees from structure.json. Pure retweets "
            "without reply links are not represented in PHEME conversation trees."
        )

    def _resolve_root(self, raw_dir: Path) -> Path | None:
        candidates = [raw_dir / "pheme", raw_dir / "PHEME", raw_dir]
        for cand in candidates:
            if cand.is_dir() and any(cand.rglob("structure.json")):
                return cand
        return None

    def is_available(self, raw_dir: Path) -> bool:
        return self._resolve_root(raw_dir) is not None

    def load(self, raw_dir: Path) -> DatasetBundle:
        root_dir = self._resolve_root(raw_dir)
        if root_dir is None:
            raise NoDatasetError(
                f"Dataset 'pheme' not found under {raw_dir}. "
                f"Place extracted PHEME event folders inside '{raw_dir / 'pheme'}'.",
                details={"expected_path": str(raw_dir / "pheme")},
            )

        structure_files = sorted(root_dir.rglob("structure.json"))
        raw_rows: list[dict[str, str | float | None]] = []
        root_timestamps: dict[str, float] = {}

        for sfile in structure_files:
            thread_dir = sfile.parent
            cascade_id = thread_dir.name
            tweet_times: dict[str, float] = {}

            for sub_name in ("source-tweet", "reactions"):
                sub_dir = thread_dir / sub_name
                if not sub_dir.is_dir():
                    continue
                for jf in sub_dir.glob("*.json"):
                    try:
                        payload = json.loads(jf.read_text(encoding="utf-8"))
                        tid = str(payload.get("id_str") or payload.get("id") or jf.stem)
                        ts = _parse_twitter_created_at(str(payload.get("created_at", "")))
                        if ts is not None:
                            tweet_times[tid] = ts
                    except (OSError, json.JSONDecodeError):
                        continue

            if cascade_id not in tweet_times:
                continue
            root_ts = tweet_times[cascade_id]
            root_timestamps[cascade_id] = root_ts

            try:
                struct_data = json.loads(sfile.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue

            pairs: list[tuple[str | None, str]] = []
            _walk_structure(struct_data, None, pairs)
            if not pairs:
                pairs.append((None, cascade_id))

            for p_id, c_id in pairs:
                if c_id not in tweet_times:
                    continue
                rel_ts = tweet_times[c_id] - root_ts
                raw_rows.append(
                    {
                        "cascade_id": cascade_id,
                        "parent_id": p_id,
                        "child_id": c_id,
                        "timestamp": float(rel_ts),
                    }
                )

        raw_df = pd.DataFrame(
            raw_rows, columns=["cascade_id", "parent_id", "child_id", "timestamp"]
        )
        cleaned_edges, validation_report = validate_and_clean_edges(raw_df)
        metadata = compute_cascade_metadata(cleaned_edges, root_timestamps)
        horizon = (
            float(metadata["observation_horizon_seconds"].max())
            if not metadata.empty
            else 0.0
        )

        return DatasetBundle(
            dataset_name=self.name,
            dataset_hash=compute_files_sha256(structure_files),
            source_description=self.source_description,
            reconstruction_note=self.reconstruction_note,
            observation_horizon_seconds=horizon,
            edges_df=cleaned_edges,
            cascade_metadata=metadata,
            validation_report=validation_report,
        )
