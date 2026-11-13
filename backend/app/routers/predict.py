"""Validation and early-window virality prediction endpoints."""

from __future__ import annotations

import json
import math
from typing import Any

import pandas as pd
from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import ValidationError as PydanticValidationError

from app.dependencies import get_store, read_validated_csv_upload
from app.errors import InvalidInputError, UnsupportedMediaTypeError
from app.schemas import (
    PredictByIdRequest,
    PredictCascadeResult,
    PredictResponse,
    ValidateResponse,
)
from app.services.explain import explain_cascade_prediction
from app.services.features import extract_cascade_features
from app.services.graph import truncate_to_window
from app.services.model_store import AppStore, LoadedModelArtifact
from app.services.validation import parse_canonical_csv, validate_and_clean_edges

router = APIRouter(prefix="/api", tags=["prediction"])


def _predict_single_cascade(
    cascade_id: str,
    cascade_df: pd.DataFrame,
    artifact: LoadedModelArtifact,
    *,
    exact_max_nodes: int,
    sample_sources: int,
    seed: int,
) -> PredictCascadeResult:
    meta = artifact.meta
    win = float(meta["early_window_seconds"])
    min_edges = int(meta.get("min_early_edges", 3))
    decision_threshold = float(meta.get("decision_threshold", 0.5))
    virality_threshold_size = int(meta["virality_threshold_size"])
    feature_names = list(meta["feature_names"])

    early_df = truncate_to_window(cascade_df, win)
    early_edges_count = int(early_df["parent_id"].notna().sum())

    if early_edges_count < min_edges:
        return PredictCascadeResult(
            cascade_id=cascade_id,
            excluded=True,
            exclusion_reason=(
                f"Excluded from prediction: only {early_edges_count} propagation edge(s) "
                f"observed within the first {win:.0f}s window (minimum {min_edges} required)."
            ),
            predicted_viral=None,
            virality_probability=None,
            decision_threshold=decision_threshold,
            virality_threshold_size=virality_threshold_size,
            early_window_seconds=win,
            top_factors=[],
            features={},
        )

    feats = extract_cascade_features(
        early_df,
        window_seconds=win,
        exact_max_nodes=exact_max_nodes,
        sample_sources=sample_sources,
        seed=seed,
    )
    row_df = pd.DataFrame([[feats[name] for name in feature_names]], columns=feature_names)
    probs = artifact.pipeline.predict_proba(row_df)
    prob = float(probs[0, 1]) if probs.shape[1] > 1 else 0.0
    predicted_viral = prob >= decision_threshold

    factors = explain_cascade_prediction(
        feats,
        feature_medians=dict(meta.get("feature_medians", {})),
        feature_iqrs=dict(meta.get("feature_iqrs", {})),
        permutation_importances=dict(meta.get("permutation_importances", {})),
    )

    clean_features = {
        k: round(float(v), 4) for k, v in feats.items() if math.isfinite(float(v))
    }

    return PredictCascadeResult(
        cascade_id=cascade_id,
        excluded=False,
        exclusion_reason=None,
        predicted_viral=predicted_viral,
        virality_probability=round(prob, 4),
        decision_threshold=decision_threshold,
        virality_threshold_size=virality_threshold_size,
        early_window_seconds=win,
        top_factors=factors,
        features=clean_features,
    )


@router.post("/validate", response_model=ValidateResponse)
async def validate_csv(
    file: UploadFile = File(...),
    store: AppStore = Depends(get_store),
) -> ValidateResponse:
    """Parse and validate a canonical edge CSV upload without running prediction."""
    raw_bytes = await read_validated_csv_upload(file, store.settings.max_upload_bytes)
    raw_df = parse_canonical_csv(raw_bytes)
    cleaned_df, report = validate_and_clean_edges(raw_df)
    cascade_ids = (
        sorted(cleaned_df["cascade_id"].astype(str).unique().tolist())
        if not cleaned_df.empty
        else []
    )
    return ValidateResponse(validation_report=report, cascade_ids=cascade_ids)


@router.post(
    "/predict",
    response_model=PredictResponse,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "application/json": {
                    "schema": {"$ref": "#/components/schemas/PredictByIdRequest"}
                },
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"],
                    }
                },
            },
        }
    },
)
async def predict_virality(
    request: Request,
    store: AppStore = Depends(get_store),
) -> PredictResponse:
    """Predict early-window virality from either `{cascade_id}` JSON or uploaded canonical CSV."""
    artifact = store.require_model()
    content_type = (request.headers.get("content-type") or "").lower()

    if "application/json" in content_type:
        body_bytes = await request.body()
        if len(body_bytes) > 65536:
            raise InvalidInputError("JSON payload too large.")
        try:
            payload_obj: Any = json.loads(body_bytes.decode("utf-8"))
            req = PredictByIdRequest.model_validate(payload_obj)
        except (UnicodeDecodeError, json.JSONDecodeError, PydanticValidationError) as exc:
            raise InvalidInputError(f"Invalid JSON request body: {exc}") from exc

        c_edges = store.get_cascade_edges(req.cascade_id)
        pred = _predict_single_cascade(
            req.cascade_id,
            c_edges,
            artifact,
            exact_max_nodes=store.settings.wiener_exact_max_nodes,
            sample_sources=store.settings.wiener_sample_sources,
            seed=store.settings.seed,
        )
        return PredictResponse(validation_report=None, predictions=[pred])

    if "multipart/form-data" in content_type:
        form = await request.form()
        upload = form.get("file")
        if upload is None or not hasattr(upload, "read"):
            raise InvalidInputError("Multipart request must include a 'file' CSV field.")
        raw_bytes = await read_validated_csv_upload(
            upload,  # type: ignore[arg-type]
            store.settings.max_upload_bytes,
        )
        raw_df = parse_canonical_csv(raw_bytes)
        cleaned_df, report = validate_and_clean_edges(raw_df)
        if not report.is_valid or cleaned_df.empty:
            raise InvalidInputError(
                "Uploaded CSV contains no valid cascades after validation.",
                details=report.model_dump(),
            )
        results: list[PredictCascadeResult] = []
        for cid, grp in cleaned_df.groupby("cascade_id", sort=True):
            results.append(
                _predict_single_cascade(
                    str(cid),
                    grp,
                    artifact,
                    exact_max_nodes=store.settings.wiener_exact_max_nodes,
                    sample_sources=store.settings.wiener_sample_sources,
                    seed=store.settings.seed,
                )
            )
        return PredictResponse(validation_report=report, predictions=results)

    raise UnsupportedMediaTypeError(
        "Content-Type must be 'application/json' (for cascade_id) or "
        "'multipart/form-data' (for CSV upload)."
    )
