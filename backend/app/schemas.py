"""Pydantic v2 data contracts and API schemas."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

CANONICAL_COLUMNS: tuple[str, str, str, str] = (
    "cascade_id",
    "parent_id",
    "child_id",
    "timestamp",
)


class ValidationReport(BaseModel):
    """Explicit validation report documenting every issue found and action taken."""

    is_valid: bool
    total_rows: int
    valid_edges: int
    cascades_count: int
    missing_columns: list[str] = Field(default_factory=list)
    malformed_rows_dropped: int = 0
    negative_timestamps_dropped: int = 0
    self_loops_dropped: int = 0
    duplicate_edges_dropped: int = 0
    multiple_parents_resolved: int = 0
    cycles_detected: int = 0
    cycle_edges_removed: int = 0
    multiple_roots_cascades: int = 0
    actions_taken: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    """API liveness and readiness status."""

    status: Literal["ok"] = "ok"
    model_loaded: bool
    dataset_loaded: bool
    active_dataset: str | None = None
    disclaimer: str = (
        "Predicts spreading behaviour from early propagation structure only, not truthfulness."
    )


class ModelInfoResponse(BaseModel):
    """Metadata for the currently loaded trained model."""

    model_name: str
    dataset_name: str
    dataset_hash: str
    feature_names: list[str]
    early_window_seconds: float
    virality_quantile: float
    virality_threshold_size: int
    min_early_edges: int
    seed: int
    split_dates: dict[str, str | None]
    training_time_seconds: float
    library_versions: dict[str, str]
    reconstruction_note: str


class CascadeSummaryItem(BaseModel):
    """Summary row for a real cascade in the loaded dataset."""

    cascade_id: str
    early_nodes: int
    early_edges: int
    final_size: int
    observation_horizon_seconds: float
    is_viral: bool | None = None
    excluded: bool = False
    exclusion_reason: str | None = None


class CascadeListResponse(BaseModel):
    """Paginated list of real cascades."""

    dataset_name: str
    early_window_seconds: float
    total: int
    limit: int
    offset: int
    items: list[CascadeSummaryItem]


class TreeNodePayload(BaseModel):
    """Node entry for propagation tree visualization."""

    id: str
    parent_id: str | None
    timestamp: float
    depth: int
    is_root: bool
    is_leaf: bool
    out_degree: int


class TreeEdgePayload(BaseModel):
    """Directed propagation edge."""

    parent_id: str
    child_id: str
    timestamp: float


class TreeGraphResponse(BaseModel):
    """Early-window propagation tree payload for a cascade."""

    cascade_id: str
    early_window_seconds: float
    root_id: str | None
    total_nodes: int
    total_edges: int
    returned_nodes: int
    truncated: bool
    truncation_notice: str | None = None
    nodes: list[TreeNodePayload]
    edges: list[TreeEdgePayload]
    stats: dict[str, float]


class FeatureFactor(BaseModel):
    """Approximate feature contribution based on global permutation importance."""

    feature: str
    value: float
    training_median: float
    importance_weight: float
    contribution_score: float
    direction: Literal["increases_virality", "decreases_virality", "neutral"]


class PredictByIdRequest(BaseModel):
    """JSON body for predicting on a cascade from the loaded dataset."""

    cascade_id: str = Field(min_length=1)


class PredictCascadeResult(BaseModel):
    """Prediction output for a single cascade."""

    cascade_id: str
    excluded: bool
    exclusion_reason: str | None = None
    predicted_viral: bool | None = None
    virality_probability: float | None = None
    decision_threshold: float
    virality_threshold_size: int
    early_window_seconds: float
    explanation_note: str = (
        "Approximate, based on global permutation importance relative to training medians."
    )
    disclaimer: str = (
        "Predicts spreading behaviour from early propagation structure only, not truthfulness."
    )
    top_factors: list[FeatureFactor] = Field(default_factory=list)
    features: dict[str, float] = Field(default_factory=dict)


class PredictResponse(BaseModel):
    """Prediction response covering one or more uploaded/selected cascades."""

    validation_report: ValidationReport | None = None
    predictions: list[PredictCascadeResult]


class ValidateResponse(BaseModel):
    """Response from POST /api/validate."""

    validation_report: ValidationReport
    cascade_ids: list[str]


class ConfidenceInterval(BaseModel):
    """95% bootstrap confidence interval."""

    low: float
    high: float


class ModelMetricsEntry(BaseModel):
    """Evaluation metrics for a single model on a split."""

    model_key: str
    display_name: str
    split_name: str
    accuracy: float
    precision: float
    recall: float
    f1: float
    roc_auc: float
    pr_auc: float
    brier_score: float
    roc_auc_ci: ConfidenceInterval | None = None
    pr_auc_ci: ConfidenceInterval | None = None
    confusion_matrix: list[list[int]]


class FeatureImportanceEntry(BaseModel):
    """Permutation vs impurity feature importance."""

    feature: str
    permutation_importance_mean: float
    permutation_importance_std: float
    impurity_importance: float | None = None
    note: str | None = None


class ThresholdSensitivityEntry(BaseModel):
    """Sensitivity analysis across virality quantiles."""

    quantile: float
    threshold_size: int
    positive_rate_train: float
    positive_rate_test: float
    rf_pr_auc: float
    rf_roc_auc: float
    rf_recall: float
    naive_pr_auc: float


class SizeHistogramBin(BaseModel):
    """Log-scale size distribution bin."""

    bin_label: str
    min_size: int
    max_size: int
    count: int


class DatasetSummaryReport(BaseModel):
    """Summary statistics of the real dataset used in training/evaluation."""

    dataset_name: str
    dataset_hash: str
    source_description: str
    reconstruction_note: str
    observation_horizon_seconds: float
    early_window_seconds: float
    total_cascades_raw: int
    eligible_cascades: int
    excluded_by_split: dict[str, int]
    split_counts: dict[str, int]
    positive_rate_by_split: dict[str, float]
    size_summary: dict[str, float]
    size_histogram_log: list[SizeHistogramBin]
    validation_report: ValidationReport


class ReportResponse(BaseModel):
    """Full evaluation report loaded directly from reports/metrics.json and curves.json."""

    dataset_summary: DatasetSummaryReport
    virality_quantile: float
    virality_threshold_size: int
    beats_naive_baseline: bool
    baseline_comparison_note: str
    temporal_test_results: list[ModelMetricsEntry]
    random_split_comparison: list[ModelMetricsEntry]
    feature_importance: list[FeatureImportanceEntry]
    threshold_sensitivity: list[ThresholdSensitivityEntry]
    curves: dict[str, Any]
    limitations: list[str]
    disclaimer: str
