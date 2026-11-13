"""Observation-window sweep experiment.

Trains the same Random Forest pipeline at several early-observation windows T and
records how predictive performance changes with observation time. Produces a
summary CSV, a per-window metrics set, and a Markdown table for slides.

This is the project's novelty experiment: it answers "how early can virality be
predicted, and where does the signal saturate?" using only structure and timing.

Run from the backend directory:

    .\.venv\Scripts\python.exe -m app.ml.experiment_window_sweep --dataset twitter15
"""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import get_settings
from app.errors import NoDatasetError
from app.ml.datasets.registry import get_adapter
from app.ml.train import run_training_pipeline

DEFAULT_WINDOWS = [300.0, 900.0, 1800.0, 3600.0, 7200.0]

def _model_entry(metrics: dict[str, Any], model_key: str) -> dict[str, Any]:
    for entry in metrics.get("temporal_test_results", []):
        if entry.get("model_key") == model_key:
            return entry
    return {}

def _backup_artifacts(settings, backup_dir: Path) -> None:
    models_dst = backup_dir / "models"
    models_dst.mkdir(parents=True, exist_ok=True)
    if settings.models_dir.exists():
        for item in settings.models_dir.iterdir():
            if item.is_file():
                shutil.copy2(item, models_dst / item.name)
    for p in (settings.metrics_path, settings.curves_path):
        if p.exists():
            shutil.copy2(p, backup_dir / p.name)

def _restore_artifacts(settings, backup_dir: Path) -> None:
    models_src = backup_dir / "models"
    if models_src.exists() and settings.models_dir.exists():
        for item in settings.models_dir.iterdir():
            if item.is_file():
                item.unlink()
        for item in models_src.iterdir():
            shutil.copy2(item, settings.models_dir / item.name)
    for name, dest in (
        ("metrics.json", settings.metrics_path),
        ("curves.json", settings.curves_path),
    ):
        src = backup_dir / name
        if src.exists():
            shutil.copy2(src, dest)

def _markdown_table(df: pd.DataFrame) -> str:
    cols = ["window_minutes", "threshold_size", "rf_pr_auc", "rf_roc_auc", "rf_recall", "naive_pr_auc", "beats_naive"]
    header = "| Window (min) | Viral threshold | RF PR-AUC | RF ROC-AUC | RF Recall | Naive PR-AUC | Beats naive? |"
    sep = "|---|---|---|---|---|---|---|"
    lines = [header, sep]
    for _, row in df.iterrows():
        lines.append(
            "| {window_minutes} | {threshold_size} | {rf_pr_auc} | {rf_roc_auc} | {rf_recall} | {naive_pr_auc} | {beats_naive} |".format(**row)
        )
    return "\n".join(lines) + "\n"

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Sweep the early-observation window and record predictive performance."
    )
    parser.add_argument("--dataset", default="twitter15", help="Dataset adapter name")
    parser.add_argument("--quantile", type=float, default=0.80, help="Virality quantile")
    parser.add_argument(
        "--windows",
        default=",".join(str(int(w)) for w in DEFAULT_WINDOWS),
        help="Comma-separated window sizes in seconds",
    )
    parser.add_argument(
        "--no-tune",
        action="store_true",
        help="Skip Random Forest grid search (faster, slightly lower performance)",
    )
    args = parser.parse_args(argv)

    windows = [float(w) for w in args.windows.split(",") if w.strip()]

    settings = get_settings()
    try:
        adapter = get_adapter(args.dataset, settings.data_raw_dir)
        bundle = adapter.load(settings.data_raw_dir)
    except NoDatasetError as exc:
        print(f"ERROR [{exc.code}]: {exc.message}")
        return 1

    out_dir = settings.reports_dir / "window_sweep"
    out_dir.mkdir(parents=True, exist_ok=True)

    backup_dir = Path(tempfile.mkdtemp(prefix="sweep_backup_"))
    _backup_artifacts(settings, backup_dir)

    rows: list[dict[str, Any]] = []
    try:
        for w in windows:
            print(f"\n=== Observation window T = {w:.0f}s ({w / 60:.1f} min) ===")
            run_training_pipeline(
                bundle,
                settings,
                window_seconds=w,
                virality_quantile=args.quantile,
                tune_rf=not args.no_tune,
            )
            metrics = json.loads(settings.metrics_path.read_text(encoding="utf-8"))
            (out_dir / f"metrics_T{int(w)}.json").write_text(
                json.dumps(metrics, indent=2), encoding="utf-8"
            )

            rf = _model_entry(metrics, "rf")
            naive = _model_entry(metrics, "naive_edges")
            rows.append(
                {
                    "window_seconds": w,
                    "window_minutes": round(w / 60.0, 1),
                    "threshold_size": metrics.get("virality_threshold_size"),
                    "rf_pr_auc": round(rf.get("pr_auc", float("nan")), 4),
                    "rf_roc_auc": round(rf.get("roc_auc", float("nan")), 4),
                    "rf_recall": round(rf.get("recall", float("nan")), 4),
                    "rf_precision": round(rf.get("precision", float("nan")), 4),
                    "rf_f1": round(rf.get("f1", float("nan")), 4),
                    "naive_pr_auc": round(naive.get("pr_auc", float("nan")), 4),
                    "beats_naive": metrics.get("beats_naive_baseline"),
                }
            )
    finally:
        _restore_artifacts(settings, backup_dir)
        shutil.rmtree(backup_dir, ignore_errors=True)

    df = pd.DataFrame(rows).sort_values("window_seconds").reset_index(drop=True)
    csv_path = out_dir / "window_sweep_summary.csv"
    md_path = out_dir / "window_sweep_summary.md"
    df.to_csv(csv_path, index=False)
    md_path.write_text(_markdown_table(df), encoding="utf-8")

    print("\n" + "=" * 78)
    print("OBSERVATION-WINDOW SWEEP RESULTS")
    print("=" * 78)
    print(df.to_string(index=False))

    valid = df.dropna(subset=["rf_pr_auc"])
    if len(valid) >= 2:
        peak = valid.loc[valid["rf_pr_auc"].idxmax()]
        first = valid.iloc[0]
        print(
            f"\nSignal: PR-AUC rises from {first['rf_pr_auc']:.3f} at "
            f"{first['window_minutes']} min to a peak of {peak['rf_pr_auc']:.3f} "
            f"at {peak['window_minutes']} min."
        )

    print(f"\nSummary CSV    -> {csv_path}")
    print(f"Markdown table -> {md_path}")
    print(f"Per-window data-> {out_dir}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())