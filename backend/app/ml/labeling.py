"""Target virality labeling fit strictly on training cascade final sizes."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd


def fit_virality_threshold(
    train_final_sizes: pd.Series | np.ndarray, quantile: float = 0.80
) -> int:
    """Compute integer virality threshold from training final sizes only.

    Rule for ties and fractional quantiles:
    A cascade is labeled highly viral iff `final_size >= ceil(quantile(train_final_sizes, q))`.
    Because `final_size` is an integer, `final_size >= ceil(x)` is equivalent to `final_size >= x`,
    and ties at the exact threshold are consistently assigned to the positive (viral) class.
    """
    if not 0.0 < quantile < 1.0:
        raise ValueError(f"Virality quantile must be in (0, 1), got {quantile}.")
    arr = np.asarray(train_final_sizes, dtype=float)
    if arr.size == 0:
        raise ValueError("Cannot fit virality threshold on an empty training set.")
    raw_q = float(np.quantile(arr, quantile))
    return int(math.ceil(raw_q))


def apply_virality_label(final_sizes: pd.Series | np.ndarray, threshold_size: int) -> np.ndarray:
    """Apply a pre-fit integer threshold (`final_size >= threshold_size`) without refitting."""
    arr = np.asarray(final_sizes, dtype=int)
    return (arr >= int(threshold_size)).astype(int)
