"""End-to-end real-data training, baseline comparison, evaluation, and artifact export."""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import UTC, datetime
from typing import Any

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GridSearchCV, StratifiedKFold
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app.config import Settings, get_settings
from app.errors import NoDatasetError
from app.ml.datasets.base import DatasetBundle
from app.ml.datasets.registry import get_adapter
from app.ml.evaluate import compute_feature_importances, evaluate_classifier
from app.ml.labeling import apply_virality_label, fit_virality_threshold
from app.ml.splitting import (
    SplitIndices,
    stratified_random_cascade_split,
    temporal_cascade_split,
)
from app.schemas import (
    DatasetSummaryReport,
    ModelMetricsEntry,
    ReportResponse,
    SizeHistogramBin,
    ThresholdSensitivityEntry,
)
from app.services.features import FEATURE_NAMES, extract_features_table


def _build_rf_pipeline(seed: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            (
                "clf",
                RandomForestClassifier(
                    n_estimators=200,
                    class_weight="balanced",
                    random_state=seed,
                    n_jobs=1,
                ),
            ),
        ]
    )


def _fit_tuned_rf(x_train: pd.DataFrame, y_train: np.ndarray, seed: int) -> Pipeline:
    base_pipe = _build_rf_pipeline(seed)
    unique, counts = np.unique(y_train, return_counts=True)
    if len(unique) < 2 or int(counts.min()) < 2 or len(x_train) < 10:
        base_pipe.fit(x_train, y_train)
        return base_pipe

    n_splits = min(5, int(counts.min()))
    cv = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed)
    param_grid = {
        "clf__n_estimators": [150, 300],
        "clf__max_depth": [None, 8, 16],
        "clf__min_samples_leaf": [1, 3],
    }
    search = GridSearchCV(
        estimator=base_pipe,
        param_grid=param_grid,
        scoring="average_precision",
        cv=cv,
        n_jobs=1,
        refit=True,
    )
    search.fit(x_train, y_train)
    best: Pipeline = search.best_estimator_
    return best


def _build_logreg_pipeline(seed: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("scaler", StandardScaler()),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=seed,
                ),
            ),
        ]
    )


def _build_dummy_pipeline(seed: int) -> Pipeline:
    return Pipeline(
        steps=[
            ("imputer", SimpleImputer(strategy="median")),
            ("clf", DummyClassifier(strategy="prior", random_state=seed)),
        ]
    )


def _build_naive_num_edges_pipeline(seed: int) -> Pipeline:
    selector = ColumnTransformer(
        transformers=[
            (
                "num_edges_only",
                Pipeline(
                    steps=[
                        ("imputer", SimpleImputer(strategy="median")),
                        ("scaler", StandardScaler()),
                    ]
                ),
                ["num_edges"],
            )
        ],
        remainder="drop",
    )
    return Pipeline(
        steps=[
            ("selector", selector),
            (
                "clf",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=1000,
                    random_state=seed,
                ),
            ),
        ]
    )


def _fit_safe(pipe: Pipeline, x_train: pd.DataFrame, y_train: np.ndarray, seed: int) -> Pipeline:
    if len(np.unique(y_train)) < 2 and hasattr(pipe.named_steps["clf"], "C"):
        # Fallback to Dummy if single-class edge fixture
        dummy = _build_dummy_pipeline(seed)
        dummy.fit(x_train, y_train)
        return dummy
    pipe.fit(x_train, y_train)
    return pipe


def _build_log_histogram(sizes: np.ndarray) -> list[SizeHistogramBin]:
    if sizes.size == 0:
        return []
    bins = [
        (1, 5, "1-5"),
        (6, 15, "6-15"),
        (16, 50, "16-50"),
        (51, 150, "51-150"),
        (151, 500, "151-500"),
        (501, 2000, "501-2000"),
        (2001, 10_000_000, "2001+"),
    ]
    result: list[SizeHistogramBin] = []
    for lo, hi, label in bins:
        cnt = int(np.sum((sizes >= lo) & (sizes <= hi)))
        result.append(SizeHistogramBin(bin_label=label, min_size=lo, max_size=hi, count=cnt))
    return result


def _format_split_date(ts: float | None) -> str | None:
    if ts is None or ts < 1_000_000_000.0:
        return None
    return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d")


def run_training_pipeline(
    bundle: DatasetBundle,
    settings: Settings,
    *,
    window_seconds: float | None = None,
    virality_quantile: float | None = None,
    tune_rf: bool = True,
) -> dict[str, Any]:
    """Run full training, baseline evaluation, sensitivity analysis, and artifact saving."""
    t_start = time.perf_counter()
    win = float(window_seconds if window_seconds is not None else settings.early_window_seconds)
    q = float(virality_quantile if virality_quantile is not None else settings.virality_quantile)
    seed = settings.seed

    feature_names = list(FEATURE_NAMES)
    edges_df = bundle.edges_df
    meta_df = bundle.cascade_metadata.copy()

    # 1. Extract early-window features for all cascades (with strict T truncation guard)
    feat_df = extract_features_table(
        edges_df,
        window_seconds=win,
        exact_max_nodes=settings.wiener_exact_max_nodes,
        sample_sources=settings.wiener_sample_sources,
        seed=seed,
    )
    merged = meta_df.merge(feat_df, on="cascade_id", how="inner")

    # 2. Temporal split on all observed cascades before checking per-split exclusions
    raw_splits = temporal_cascade_split(
        merged[["cascade_id", "root_timestamp", "final_size"]],
        train_ratio=settings.train_ratio,
        val_ratio=settings.val_ratio,
    )
    merged["eligible"] = merged["num_edges"] >= float(settings.min_early_edges)

    eligible_set = set(merged.loc[merged["eligible"], "cascade_id"].astype(str))
    train_ids = [cid for cid in raw_splits.train_ids if cid in eligible_set]
    val_ids = [cid for cid in raw_splits.val_ids if cid in eligible_set]
    test_ids = [cid for cid in raw_splits.test_ids if cid in eligible_set]

    excluded_by_split = {
        "train": len(raw_splits.train_ids) - len(train_ids),
        "val": len(raw_splits.val_ids) - len(val_ids),
        "test": len(raw_splits.test_ids) - len(test_ids),
    }

    if len(train_ids) < 3 or len(test_ids) < 1:
        raise ValueError(
            f"Too few eligible cascades after early-window >= {settings.min_early_edges} "
            f"edge filter (train={len(train_ids)}, val={len(val_ids)}, test={len(test_ids)})."
        )

    indexed = merged.set_index("cascade_id")

    # 3. Fit virality threshold strictly on eligible training final sizes
    train_sizes = indexed.loc[train_ids, "final_size"].to_numpy()
    threshold_size = fit_virality_threshold(train_sizes, quantile=q)

    x_train = indexed.loc[train_ids, feature_names]
    y_train = apply_virality_label(indexed.loc[train_ids, "final_size"].to_numpy(), threshold_size)
    y_val = (
        apply_virality_label(indexed.loc[val_ids, "final_size"].to_numpy(), threshold_size)
        if val_ids
        else np.array([], dtype=int)
    )
    x_test = indexed.loc[test_ids, feature_names]
    y_test = apply_virality_label(indexed.loc[test_ids, "final_size"].to_numpy(), threshold_size)

    # 4. Fit all 4 models strictly on train
    rf_model = _fit_tuned_rf(x_train, y_train, seed) if tune_rf else _fit_safe(
        _build_rf_pipeline(seed), x_train, y_train, seed
    )
    logreg_model = _fit_safe(_build_logreg_pipeline(seed), x_train, y_train, seed)
    dummy_model = _fit_safe(_build_dummy_pipeline(seed), x_train, y_train, seed)
    naive_model = _fit_safe(_build_naive_num_edges_pipeline(seed), x_train, y_train, seed)

    models_spec = [
        ("rf", "Random Forest (all early features)", rf_model),
        ("logreg", "Logistic Regression (all early features)", logreg_model),
        ("naive_edges", "Naive Baseline (num_edges only)", naive_model),
        ("dummy", "Dummy Prior Baseline", dummy_model),
    ]

    temporal_results: list[ModelMetricsEntry] = []
    curves_payload: dict[str, Any] = {"temporal_test": {}, "random_test": {}}

    for key, label, model in models_spec:
        entry, curve_data = evaluate_classifier(
            model,
            x_test,
            y_test,
            model_key=key,
            display_name=label,
            split_name="temporal_test",
            n_bootstrap=settings.bootstrap_iterations,
            seed=seed,
        )
        temporal_results.append(entry)
        curves_payload["temporal_test"][key] = curve_data

    # 5. Permutation importance on temporal test set
    feat_importances = compute_feature_importances(
        rf_model, x_test, y_test, feature_names, seed=seed
    )

    # 6. Stratified random split comparison (clearly labelled optimistic)
    eligible_ids = train_ids + val_ids + test_ids
    eligible_df = indexed.loc[eligible_ids]
    elig_labels_approx = apply_virality_label(
        eligible_df["final_size"].to_numpy(), threshold_size
    )
    rand_splits: SplitIndices = stratified_random_cascade_split(
        eligible_ids,
        elig_labels_approx,
        train_ratio=settings.train_ratio,
        val_ratio=settings.val_ratio,
        seed=seed,
    )
    rand_thresh = fit_virality_threshold(
        indexed.loc[rand_splits.train_ids, "final_size"].to_numpy(), quantile=q
    )
    xr_train = indexed.loc[rand_splits.train_ids, feature_names]
    yr_train = apply_virality_label(
        indexed.loc[rand_splits.train_ids, "final_size"].to_numpy(), rand_thresh
    )
    xr_test = indexed.loc[rand_splits.test_ids, feature_names]
    yr_test = apply_virality_label(
        indexed.loc[rand_splits.test_ids, "final_size"].to_numpy(), rand_thresh
    )

    rf_rand = _fit_safe(_build_rf_pipeline(seed), xr_train, yr_train, seed)
    naive_rand = _fit_safe(_build_naive_num_edges_pipeline(seed), xr_train, yr_train, seed)
    random_results: list[ModelMetricsEntry] = []
    for key, label, model in [
        ("rf", "Random Forest (optimistic random split)", rf_rand),
        ("naive_edges", "Naive Baseline (optimistic random split)", naive_rand),
    ]:
        entry, curve_data = evaluate_classifier(
            model,
            xr_test,
            yr_test,
            model_key=key,
            display_name=label,
            split_name="random_test_optimistic",
            n_bootstrap=settings.bootstrap_iterations,
            seed=seed,
        )
        random_results.append(entry)
        curves_payload["random_test"][key] = curve_data

    # 7. Threshold sensitivity at q = 0.80, 0.90, 0.95
    sensitivity: list[ThresholdSensitivityEntry] = []
    for sq in settings.sensitivity_quantiles:
        s_thresh = fit_virality_threshold(train_sizes, quantile=sq)
        sy_train = apply_virality_label(indexed.loc[train_ids, "final_size"].to_numpy(), s_thresh)
        sy_test = apply_virality_label(indexed.loc[test_ids, "final_size"].to_numpy(), s_thresh)

        s_rf = _fit_safe(_build_rf_pipeline(seed), x_train, sy_train, seed)
        s_naive = _fit_safe(_build_naive_num_edges_pipeline(seed), x_train, sy_train, seed)
        rf_m, _ = evaluate_classifier(
            s_rf,
            x_test,
            sy_test,
            model_key="rf",
            display_name="RF",
            split_name="temporal_test",
            n_bootstrap=100,
            seed=seed,
        )
        nv_m, _ = evaluate_classifier(
            s_naive,
            x_test,
            sy_test,
            model_key="naive_edges",
            display_name="Naive",
            split_name="temporal_test",
            n_bootstrap=100,
            seed=seed,
        )
        sensitivity.append(
            ThresholdSensitivityEntry(
                quantile=float(sq),
                threshold_size=int(s_thresh),
                positive_rate_train=float(np.mean(sy_train)),
                positive_rate_test=float(np.mean(sy_test)),
                rf_pr_auc=rf_m.pr_auc,
                rf_roc_auc=rf_m.roc_auc,
                rf_recall=rf_m.recall,
                naive_pr_auc=nv_m.pr_auc,
            )
        )

    # 8. Comparison check vs naive baseline
    rf_temporal = next(m for m in temporal_results if m.model_key == "rf")
    naive_temporal = next(m for m in temporal_results if m.model_key == "naive_edges")
    beats_naive = rf_temporal.pr_auc > naive_temporal.pr_auc
    if beats_naive:
        diff = rf_temporal.pr_auc - naive_temporal.pr_auc
        baseline_note = (
            f"Random Forest outperformed the naive num_edges-only baseline on temporal test PR-AUC "
            f"({rf_temporal.pr_auc:.3f} vs {naive_temporal.pr_auc:.3f}, +{diff:.3f})."
        )
    else:
        baseline_note = (
            "WARNING: Random Forest did NOT beat the naive num_edges-only baseline on temporal "
            f"test PR-AUC ({rf_temporal.pr_auc:.3f} vs {naive_temporal.pr_auc:.3f}). "
            f"Structural topology added no measurable lift over early volume alone at T={win:.0f}s."
        )

    all_final_sizes = merged["final_size"].to_numpy(dtype=float)
    train_ts = indexed.loc[train_ids, "root_timestamp"].to_numpy(dtype=float)
    val_ts = (
        indexed.loc[val_ids, "root_timestamp"].to_numpy(dtype=float)
        if val_ids
        else np.array([])
    )
    test_ts = indexed.loc[test_ids, "root_timestamp"].to_numpy(dtype=float)

    split_dates = {
        "train_start": _format_split_date(float(train_ts.min())) if train_ts.size else None,
        "train_end": _format_split_date(float(train_ts.max())) if train_ts.size else None,
        "val_start": _format_split_date(float(val_ts.min())) if val_ts.size else None,
        "val_end": _format_split_date(float(val_ts.max())) if val_ts.size else None,
        "test_start": _format_split_date(float(test_ts.min())) if test_ts.size else None,
        "test_end": _format_split_date(float(test_ts.max())) if test_ts.size else None,
    }

    dataset_summary = DatasetSummaryReport(
        dataset_name=bundle.dataset_name,
        dataset_hash=bundle.dataset_hash,
        source_description=bundle.source_description,
        reconstruction_note=bundle.reconstruction_note,
        observation_horizon_seconds=bundle.observation_horizon_seconds,
        early_window_seconds=win,
        total_cascades_raw=int(len(merged)),
        eligible_cascades=int(len(eligible_ids)),
        excluded_by_split=excluded_by_split,
        split_counts={"train": len(train_ids), "val": len(val_ids), "test": len(test_ids)},
        positive_rate_by_split={
            "train": float(np.mean(y_train)),
            "val": float(np.mean(y_val)) if y_val.size else 0.0,
            "test": float(np.mean(y_test)),
        },
        size_summary={
            "min": float(np.min(all_final_sizes)),
            "median": float(np.median(all_final_sizes)),
            "p90": float(np.percentile(all_final_sizes, 90)),
            "max": float(np.max(all_final_sizes)),
            "mean": float(np.mean(all_final_sizes)),
        },
        size_histogram_log=_build_log_histogram(all_final_sizes),
        validation_report=bundle.validation_report,
    )

    limitations = [
        "Evidence comes strictly from the specific public dataset and time period loaded; "
        "results do not generalize automatically across platforms or eras.",
        "Private-channel sharing (e.g., direct messages, WhatsApp/Telegram) is unobserved.",
        "Structure-only models exclude tweet text, media, seed-account follower count, and "
        "external amplification, creating an inherent performance ceiling.",
        "Predicted virality measures spreading behaviour, never truthfulness; "
        "fast-spreading true news also scores high.",
        "Thresholds and probability calibration drift as platform UI and sharing behaviour evolve.",
        "Dual-use risk: virality predictors can guide amplification of misleading content.",
    ]

    report = ReportResponse(
        dataset_summary=dataset_summary,
        virality_quantile=q,
        virality_threshold_size=threshold_size,
        beats_naive_baseline=beats_naive,
        baseline_comparison_note=baseline_note,
        temporal_test_results=temporal_results,
        random_split_comparison=random_results,
        feature_importance=feat_importances,
        threshold_sensitivity=sensitivity,
        curves=curves_payload,
        limitations=limitations,
        disclaimer=(
            "This system predicts propagation behaviour from early graph structure and "
            "timestamps only. It does not evaluate truthfulness and must not be used for "
            "fake-news or rumor verification."
        ),
    )

    training_time = float(time.perf_counter() - t_start)

    # 9. Persist processed features, model joblib + meta.json, and reports/
    settings.data_processed_dir.mkdir(parents=True, exist_ok=True)
    settings.models_dir.mkdir(parents=True, exist_ok=True)
    settings.reports_dir.mkdir(parents=True, exist_ok=True)

    merged.to_csv(
        settings.data_processed_dir / f"{bundle.dataset_name}_features.csv", index=False
    )

    model_path = settings.models_dir / f"{bundle.dataset_name}_rf.joblib"
    meta_path = settings.models_dir / f"{bundle.dataset_name}_rf.meta.json"
    joblib.dump(rf_model, model_path)

    feature_medians: dict[str, float] = {}
    feature_iqrs: dict[str, float] = {}
    for col in feature_names:
        col_vals = x_train[col].dropna().to_numpy(dtype=float)
        if col_vals.size == 0:
            feature_medians[col] = 0.0
            feature_iqrs[col] = 1.0
        else:
            feature_medians[col] = float(np.median(col_vals))
            iqr = float(np.percentile(col_vals, 75) - np.percentile(col_vals, 25))
            std = float(np.std(col_vals))
            feature_iqrs[col] = iqr if iqr > 1e-9 else (std if std > 1e-9 else 1.0)

    meta_payload = {
        "model_name": "RandomForestClassifier",
        "dataset_name": bundle.dataset_name,
        "dataset_hash": bundle.dataset_hash,
        "feature_names": feature_names,
        "early_window_seconds": win,
        "virality_quantile": q,
        "virality_threshold_size": threshold_size,
        "decision_threshold": 0.5,
        "min_early_edges": settings.min_early_edges,
        "seed": seed,
        "split_dates": split_dates,
        "training_time_seconds": round(training_time, 3),
        "library_versions": {
            "python": platform.python_version(),
            "scikit_learn": sklearn.__version__,
            "pandas": pd.__version__,
            "numpy": np.__version__,
            "joblib": joblib.__version__,
        },
        "reconstruction_note": bundle.reconstruction_note,
        "feature_medians": feature_medians,
        "feature_iqrs": feature_iqrs,
        "permutation_importances": {
            e.feature: e.permutation_importance_mean for e in feat_importances
        },
    }
    meta_path.write_text(json.dumps(meta_payload, indent=2), encoding="utf-8")

    # Pointer to active model for startup loading
    active_pointer = {
        "dataset_name": bundle.dataset_name,
        "model_file": model_path.name,
        "meta_file": meta_path.name,
    }
    (settings.models_dir / "active_model.json").write_text(
        json.dumps(active_pointer, indent=2), encoding="utf-8"
    )

    metrics_dict = report.model_dump()
    settings.metrics_path.write_text(json.dumps(metrics_dict, indent=2), encoding="utf-8")
    settings.curves_path.write_text(json.dumps(curves_payload, indent=2), encoding="utf-8")

    return {
        "model_path": str(model_path),
        "meta_path": str(meta_path),
        "metrics_path": str(settings.metrics_path),
        "threshold_size": threshold_size,
        "rf_pr_auc": rf_temporal.pr_auc,
        "naive_pr_auc": naive_temporal.pr_auc,
        "beats_naive_baseline": beats_naive,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Train and evaluate Cascade Virality Predictor on a real dataset."
    )
    parser.add_argument(
        "--dataset",
        required=True,
        help="Dataset adapter name (e.g. twitter15, twitter16, pheme)",
    )
    parser.add_argument(
        "--window",
        type=float,
        default=None,
        help="Early observation window T in seconds",
    )
    parser.add_argument(
        "--quantile",
        type=float,
        default=None,
        help="Training final-size quantile q (default 0.80)",
    )
    args = parser.parse_args(argv)

    settings = get_settings()
    try:
        adapter = get_adapter(args.dataset, settings.data_raw_dir)
        bundle = adapter.load(settings.data_raw_dir)
    except NoDatasetError as exc:
        print(f"ERROR [{exc.code}]: {exc.message}")
        return 1

    result = run_training_pipeline(
        bundle,
        settings,
        window_seconds=args.window,
        virality_quantile=args.quantile,
        tune_rf=True,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
