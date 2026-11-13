"""Endpoints for listing and inspecting real cascades in the active dataset."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_store
from app.schemas import CascadeListResponse, CascadeSummaryItem, TreeGraphResponse
from app.services.features import extract_cascade_features
from app.services.graph import serialize_tree_for_api, truncate_to_window
from app.services.model_store import AppStore

router = APIRouter(prefix="/api", tags=["cascades"])


@router.get("/cascades", response_model=CascadeListResponse)
def list_cascades(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    store: AppStore = Depends(get_store),
) -> CascadeListResponse:
    """List real cascades from the loaded dataset with early size and final-size label."""
    bundle = store.require_dataset()
    win = store.effective_window_seconds()
    min_edges = store.settings.min_early_edges

    meta = bundle.cascade_metadata
    if search:
        term = search.strip().lower()
        meta = meta.loc[meta["cascade_id"].astype(str).str.lower().str.contains(term, regex=False)]

    total = int(len(meta))
    page = meta.iloc[offset : offset + limit]

    threshold_size: int | None = None
    if store.model is not None:
        threshold_size = int(store.model.meta["virality_threshold_size"])
        min_edges = int(store.model.meta.get("min_early_edges", min_edges))

    items: list[CascadeSummaryItem] = []
    for row in page.itertuples(index=False):
        cid = str(row.cascade_id)
        final_size = int(row.final_size)
        horizon = float(row.observation_horizon_seconds)

        c_edges = store.get_cascade_edges(cid)
        early = truncate_to_window(c_edges, win)
        early_edge_count = int(early["parent_id"].notna().sum())
        early_nodes_set = set(early["child_id"].astype(str)) | set(
            early.loc[early["parent_id"].notna(), "parent_id"].astype(str)
        )
        early_node_count = len(early_nodes_set)

        excluded = early_edge_count < min_edges
        exclusion_reason = (
            f"Excluded: only {early_edge_count} edge(s) observed in first {win:.0f}s "
            f"(minimum {min_edges} required)."
            if excluded
            else None
        )
        is_viral = (final_size >= threshold_size) if threshold_size is not None else None

        items.append(
            CascadeSummaryItem(
                cascade_id=cid,
                early_nodes=early_node_count,
                early_edges=early_edge_count,
                final_size=final_size,
                observation_horizon_seconds=horizon,
                is_viral=is_viral,
                excluded=excluded,
                exclusion_reason=exclusion_reason,
            )
        )

    return CascadeListResponse(
        dataset_name=bundle.dataset_name,
        early_window_seconds=win,
        total=total,
        limit=limit,
        offset=offset,
        items=items,
    )


@router.get("/cascades/{cascade_id}", response_model=TreeGraphResponse)
def get_cascade_tree(
    cascade_id: str,
    store: AppStore = Depends(get_store),
) -> TreeGraphResponse:
    """Return early-window propagation nodes, edges, and summary graph stats for one cascade."""
    c_edges = store.get_cascade_edges(cascade_id)
    win = store.effective_window_seconds()
    stats = extract_cascade_features(
        c_edges,
        window_seconds=win,
        exact_max_nodes=store.settings.wiener_exact_max_nodes,
        sample_sources=store.settings.wiener_sample_sources,
        seed=store.settings.seed,
    )
    # Replace NaN with -1 or omit? Keep finite dict values for clean JSON serialization
    clean_stats = {
        k: round(float(v), 4)
        for k, v in stats.items()
        if v == v  # excludes NaN cleanly
    }
    return serialize_tree_for_api(
        cascade_id=cascade_id,
        cascade_df=c_edges,
        window_seconds=win,
        stats=clean_stats,
        max_nodes=store.settings.max_tree_nodes_response,
    )
