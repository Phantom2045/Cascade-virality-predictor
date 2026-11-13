"""Approximate prediction explanation using global permutation importance vs training medians."""

from __future__ import annotations

import math
from typing import Literal

from app.schemas import FeatureFactor


def explain_cascade_prediction(
    features: dict[str, float],
    feature_medians: dict[str, float],
    feature_iqrs: dict[str, float],
    permutation_importances: dict[str, float],
    *,
    top_k: int = 6,
) -> list[FeatureFactor]:
    """Rank features by permutation importance * standardized deviation from training median."""
    factors: list[FeatureFactor] = []
    for fname, raw_val in features.items():
        val = float(raw_val)
        median = float(feature_medians.get(fname, 0.0))
        if not math.isfinite(val):
            val = median
        scale = float(feature_iqrs.get(fname, 1.0))
        if scale <= 1e-9:
            scale = 1.0
        importance = float(permutation_importances.get(fname, 0.0))
        standardized_diff = (val - median) / scale
        contribution = abs(importance) * standardized_diff

        direction: Literal["increases_virality", "decreases_virality", "neutral"]
        if abs(contribution) < 1e-6:
            direction = "neutral"
        elif contribution > 0:
            direction = "increases_virality"
        else:
            direction = "decreases_virality"

        factors.append(
            FeatureFactor(
                feature=fname,
                value=round(val, 4),
                training_median=round(median, 4),
                importance_weight=round(importance, 5),
                contribution_score=round(contribution, 5),
                direction=direction,
            )
        )

    factors.sort(key=lambda f: abs(f.contribution_score), reverse=True)
    return factors[:top_k]
