"""Evaluation metrics, bootstrap confidence intervals, curves, and permutation importance."""

from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from app.schemas import ConfidenceInterval, FeatureImportanceEntry, ModelMetricsEntry


def _safe_roc_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    if len(np.unique(y_true)) < 2:
        return 0.5
    return float(roc_auc_score(y_true, y_prob))


def _safe_pr_auc(y_true: np.ndarray, y_prob: np.ndarray) -> float:
    if int(np.sum(y_true)) == 0:
        return 0.0
    return float(average_precision_score(y_true, y_prob))


def bootstrap_auc_cis(
    y_true: np.ndarray,
    y_prob: np.ndarray,
    *,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> tuple[ConfidenceInterval, ConfidenceInterval]:
    """Compute percentile 95% bootstrap confidence intervals for ROC-AUC and PR-AUC."""
    n = len(y_true)
    if n < 4 or len(np.unique(y_true)) < 2:
        roc = _safe_roc_auc(y_true, y_prob)
        pr = _safe_pr_auc(y_true, y_prob)
        return ConfidenceInterval(low=roc, high=roc), ConfidenceInterval(low=pr, high=pr)

    rng = np.random.default_rng(seed)
    roc_scores: list[float] = []
    pr_scores: list[float] = []

    for _ in range(n_bootstrap):
        idx = rng.integers(0, n, size=n)
        yt = y_true[idx]
        yp = y_prob[idx]
        if len(np.unique(yt)) < 2:
            continue
        roc_scores.append(float(roc_auc_score(yt, yp)))
        pr_scores.append(float(average_precision_score(yt, yp)))

    if not roc_scores:
        roc = _safe_roc_auc(y_true, y_prob)
        pr = _safe_pr_auc(y_true, y_prob)
        return ConfidenceInterval(low=roc, high=roc), ConfidenceInterval(low=pr, high=pr)

    roc_low, roc_high = np.percentile(roc_scores, [2.5, 97.5])
    pr_low, pr_high = np.percentile(pr_scores, [2.5, 97.5])
    return (
        ConfidenceInterval(low=float(roc_low), high=float(roc_high)),
        ConfidenceInterval(low=float(pr_low), high=float(pr_high)),
    )


def evaluate_classifier(
    model: BaseEstimator,
    x_eval: pd.DataFrame,
    y_eval: np.ndarray,
    *,
    model_key: str,
    display_name: str,
    split_name: str,
    n_bootstrap: int = 500,
    seed: int = 42,
) -> tuple[ModelMetricsEntry, dict[str, Any]]:
    """Evaluate a fitted classifier pipeline and produce metrics + curve arrays."""
    probs_raw = model.predict_proba(x_eval)  # type: ignore[attr-defined]
    if probs_raw.shape[1] == 1:
        y_prob = np.zeros(len(x_eval), dtype=float)
    else:
        y_prob = np.asarray(probs_raw[:, 1], dtype=float)

    y_pred = (y_prob >= 0.5).astype(int)
    cm = confusion_matrix(y_eval, y_pred, labels=[0, 1]).tolist()

    roc_auc = _safe_roc_auc(y_eval, y_prob)
    pr_auc = _safe_pr_auc(y_eval, y_prob)
    roc_ci, pr_ci = bootstrap_auc_cis(y_eval, y_prob, n_bootstrap=n_bootstrap, seed=seed)

    entry = ModelMetricsEntry(
        model_key=model_key,
        display_name=display_name,
        split_name=split_name,
        accuracy=float(accuracy_score(y_eval, y_pred)),
        precision=float(precision_score(y_eval, y_pred, zero_division=0)),
        recall=float(recall_score(y_eval, y_pred, zero_division=0)),
        f1=float(f1_score(y_eval, y_pred, zero_division=0)),
        roc_auc=roc_auc,
        pr_auc=pr_auc,
        brier_score=float(brier_score_loss(y_eval, y_prob)),
        roc_auc_ci=roc_ci,
        pr_auc_ci=pr_ci,
        confusion_matrix=[[int(v) for v in row] for row in cm],
    )

    curves: dict[str, Any] = {}
    if len(np.unique(y_eval)) >= 2:
        fpr, tpr, _ = roc_curve(y_eval, y_prob)
        prec, rec, _ = precision_recall_curve(y_eval, y_prob)
        prob_true, prob_pred = calibration_curve(
            y_eval, y_prob, n_bins=min(8, max(2, len(y_eval) // 10)), strategy="quantile"
        )
        curves = {
            "roc": {"fpr": [float(x) for x in fpr], "tpr": [float(x) for x in tpr]},
            "pr": {"recall": [float(x) for x in rec], "precision": [float(x) for x in prec]},
            "calibration": {
                "prob_pred": [float(x) for x in prob_pred],
                "prob_true": [float(x) for x in prob_true],
            },
        }
    else:
        mean_pos = float(np.mean(y_eval))
        curves = {
            "roc": {"fpr": [0.0, 1.0], "tpr": [0.0, 1.0]},
            "pr": {"recall": [0.0, 1.0], "precision": [mean_pos, mean_pos]},
            "calibration": {"prob_pred": [], "prob_true": []},
        }

    return entry, curves


def compute_feature_importances(
    rf_pipeline: Any,
    x_test: pd.DataFrame,
    y_test: np.ndarray,
    feature_names: list[str],
    *,
    seed: int = 42,
) -> list[FeatureImportanceEntry]:
    """Compute test-set permutation importance alongside Random Forest impurity importance."""
    rf_step = rf_pipeline.named_steps["clf"]
    impurity = np.asarray(rf_step.feature_importances_, dtype=float)

    if len(np.unique(y_test)) >= 2 and len(x_test) >= 4:
        perm = permutation_importance(
            rf_pipeline,
            x_test,
            y_test,
            scoring="average_precision",
            n_repeats=10,
            random_state=seed,
            n_jobs=1,
        )
        perm_mean = np.asarray(perm.importances_mean, dtype=float)
        perm_std = np.asarray(perm.importances_std, dtype=float)
    else:
        perm_mean = np.zeros(len(feature_names), dtype=float)
        perm_std = np.zeros(len(feature_names), dtype=float)

    entries: list[FeatureImportanceEntry] = []
    for idx, fname in enumerate(feature_names):
        note = (
            "Clustering is always 0.0 on trees (flagged as uninformative rather than hidden)."
            if fname == "clustering_coefficient"
            else None
        )
        m_val = float(perm_mean[idx]) if math.isfinite(float(perm_mean[idx])) else 0.0
        s_val = float(perm_std[idx]) if math.isfinite(float(perm_std[idx])) else 0.0
        imp_val = float(impurity[idx]) if math.isfinite(float(impurity[idx])) else 0.0
        entries.append(
            FeatureImportanceEntry(
                feature=fname,
                permutation_importance_mean=m_val,
                permutation_importance_std=s_val,
                impurity_importance=imp_val,
                note=note,
            )
        )

    entries.sort(key=lambda e: abs(e.permutation_importance_mean), reverse=True)
    return entries
