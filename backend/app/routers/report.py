"""Model evaluation report endpoint backed strictly by reports/metrics.json."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.dependencies import get_store
from app.schemas import ReportResponse
from app.services.model_store import AppStore

router = APIRouter(prefix="/api", tags=["report"])


@router.get("/report", response_model=ReportResponse)
def get_report(store: AppStore = Depends(get_store)) -> ReportResponse:
    """Return evaluation report and dataset summary generated from a real training run."""
    return store.require_report()
