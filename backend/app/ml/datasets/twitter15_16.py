"""Adapter for Ma et al. Twitter15 and Twitter16 propagation-tree datasets."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pandas as pd

from app.errors import NoDatasetError
from app.ml.datasets.base import (
    DatasetBundle,
    compute_cascade_metadata,
    compute_files_sha256,
)
from app.services.validation import validate_and_clean_edges

_TWITTER_SNOWFLAKE_EPOCH_MS = 1288834974657
_EDGE_LINE_RE = re.compile(r"^\s*(\[.*?\])\s*->\s*(\[.*?\])\s*$")


def twitter_snowflake_to_epoch_seconds(tweet_id: str, fallback_index: int) -> float:
    """Extract creation timestamp (UTC seconds) from a Twitter Snowflake ID if valid."""
    try:
        tid = int(tweet_id)
        if tid > 100_000_000_000_000_000:
            ms = (tid >> 22) + _TWITTER_SNOWFLAKE_EPOCH_MS
            return float(ms) / 1000.0
    except ValueError:
        pass
    return float(fallback_index)


def _parse_node_tuple(raw_tuple: str) -> tuple[str, str, float] | None:
    try:
        parsed = ast.literal_eval(raw_tuple)
    except (SyntaxError, ValueError):
        return None
    if not isinstance(parsed, (list, tuple)) or len(parsed) < 3:
        return None
    uid = str(parsed[0]).strip()
    tid = str(parsed[1]).strip()
    try:
        delay_minutes = float(parsed[2])
    except (TypeError, ValueError):
        return None
    return uid, tid, delay_minutes * 60.0


class Twitter1516Adapter:
    """Load Ma et al. Twitter15 or Twitter16 tree/*.txt files into canonical edges.

    Notes on definition & data loss:
    - Veracity labels (`label.txt`) and tweet text (`source_tweets.txt`) are deliberately ignored.
    - Each `tree/<cascade_id>.txt` line encodes `parent_tuple -> child_tuple` where each tuple
      is `[uid, tweet_id, delay_minutes]`.
    - `'ROOT'` parent markers are mapped to `parent_id = None` on the root tweet.
    - Node IDs use `tweet_id` when distinct from `'ROOT'`, falling back to `uid` if needed.
    - Delays in minutes are converted to seconds since root (`delay_minutes * 60`).
    - Root creation times for temporal splitting are decoded from Twitter Snowflake IDs.
    """

    def __init__(self, variant: str = "twitter15") -> None:
        if variant not in {"twitter15", "twitter16"}:
            raise ValueError(f"Unsupported Twitter variant: {variant}")
        self.name = variant
        self.source_description = (
            f"Ma et al. {variant.upper()} propagation-tree dataset (tree structure & relative "
            "timestamps only; veracity labels and tweet text excluded)."
        )
        self.reconstruction_note = (
            "Uses explicit parent-child propagation links recorded in tree/<id>.txt "
            "(retweets/replies). Note: Twitter API hydration constraints mean user profile "
            "features are excluded and some deleted branches may be absent from the original "
            "collection; delays are recorded at minute precision."
        )

    def _resolve_tree_dir(self, raw_dir: Path) -> Path | None:
        candidates = [
            raw_dir / self.name / "tree",
            raw_dir / self.name.capitalize() / "tree",
            raw_dir / "tree",
        ]
        for cand in candidates:
            if cand.is_dir() and any(cand.glob("*.txt")):
                return cand
        return None

    def is_available(self, raw_dir: Path) -> bool:
        return self._resolve_tree_dir(raw_dir) is not None

    def load(self, raw_dir: Path) -> DatasetBundle:
        tree_dir = self._resolve_tree_dir(raw_dir)
        if tree_dir is None:
            raise NoDatasetError(
                f"Dataset '{self.name}' not found under {raw_dir}. "
                f"Place Ma et al. tree/*.txt files in '{raw_dir / self.name / 'tree'}'.",
                details={"expected_path": str(raw_dir / self.name / "tree")},
            )

        tree_files = sorted(tree_dir.glob("*.txt"))
        raw_rows: list[dict[str, str | float | None]] = []
        root_timestamps: dict[str, float] = {}

        for idx, file_path in enumerate(tree_files):
            cascade_id = file_path.stem
            root_timestamps[cascade_id] = twitter_snowflake_to_epoch_seconds(cascade_id, idx)

            with file_path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    match = _EDGE_LINE_RE.match(line)
                    if not match:
                        continue
                    parent_parsed = _parse_node_tuple(match.group(1))
                    child_parsed = _parse_node_tuple(match.group(2))
                    if parent_parsed is None or child_parsed is None:
                        continue

                    p_uid, p_tid, _p_sec = parent_parsed
                    c_uid, c_tid, c_sec = child_parsed

                    if c_tid.upper() == "ROOT":
                        continue

                    child_node = c_tid if c_tid else c_uid
                    if p_tid.upper() == "ROOT" or p_uid.upper() == "ROOT":
                        parent_node: str | None = None
                    else:
                        parent_node = p_tid if p_tid else p_uid

                    raw_rows.append(
                        {
                            "cascade_id": cascade_id,
                            "parent_id": parent_node,
                            "child_id": child_node,
                            "timestamp": float(c_sec),
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
            dataset_hash=compute_files_sha256(tree_files),
            source_description=self.source_description,
            reconstruction_note=self.reconstruction_note,
            observation_horizon_seconds=horizon,
            edges_df=cleaned_edges,
            cascade_metadata=metadata,
            validation_report=validation_report,
        )
