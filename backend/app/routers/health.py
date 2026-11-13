"""Health and model metadata endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_store
from app.schemas import HealthResponse, ModelInfoResponse
from app.services.model_store import AppStore

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health", response_model=HealthResponse)
def get_health(store: AppStore = Depends(get_store)) -> HealthResponse:
    """Return service liveness plus whether a trained model and real dataset are loaded."""
    return HealthResponse(
        status="ok",
        model_loaded=store.model is not None,
        dataset_loaded=store.dataset is not None,
        active_dataset=store.effective_dataset_name(),
    )


@router.get("/model/info", response_model=ModelInfoResponse)
def get_model_info(store: AppStore = Depends(get_store)) -> ModelInfoResponse:
    """Return provenance and hyperparameters of the active trained model."""
    artifact = store.require_model()
    meta = artifact.meta
    return ModelInfoResponse(
        model_name=str(meta["model_name"]),
        dataset_name=str(meta["dataset_name"]),
        dataset_hash=str(meta["dataset_hash"]),
        feature_names=list(meta["feature_names"]),
        early_window_seconds=float(meta["early_window_seconds"]),
        virality_quantile=float(meta["virality_quantile"]),
        virality_threshold_size=int(meta["virality_threshold_size"]),
        min_early_edges=int(meta["min_early_edges"]),
        seed=int(meta["seed"]),
        split_dates=dict(meta.get("split_dates", {})),
        training_time_seconds=float(meta["training_time_seconds"]),
        library_versions=dict(meta.get("library_versions", {})),
        reconstruction_note=str(meta.get("reconstruction_note", "")),
    )
