"""FastAPI application entrypoint with CORS, request IDs, startup caching, and error envelope."""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from app.config import Settings, get_settings
from app.errors import register_exception_handlers
from app.logging_config import configure_logging, request_id_var
from app.routers import cascades, health, predict, report
from app.schemas import PredictByIdRequest
from app.services.model_store import AppStore

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    cfg = settings or get_settings()
    configure_logging()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        store = AppStore(settings=cfg)
        store.reload()
        app.state.store = store
        logger.info(
            "Startup complete model_loaded=%s dataset_loaded=%s",
            store.model is not None,
            store.dataset is not None,
        )
        yield

    app = FastAPI(
        title="Cascade Virality Predictor API",
        version="0.1.0",
        description=(
            "Predicts early propagation virality from graph structure and edge timestamps only. "
            "Does not assess truthfulness."
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(cfg.cors_origins),
        allow_credentials=False,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["Content-Type", "X-Request-ID"],
    )

    @app.middleware("http")
    async def request_context_middleware(
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        req_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
        request.state.request_id = req_id
        token = request_id_var.set(req_id)
        start = time.perf_counter()
        try:
            response = await call_next(request)
            elapsed_ms = (time.perf_counter() - start) * 1000.0
            response.headers["X-Request-ID"] = req_id
            logger.info(
                "%s %s status=%s duration_ms=%.1f",
                request.method,
                request.url.path,
                response.status_code,
                elapsed_ms,
            )
            return response
        finally:
            request_id_var.reset(token)

    register_exception_handlers(app)

    app.include_router(health.router)
    app.include_router(cascades.router)
    app.include_router(predict.router)
    app.include_router(report.router)

    def custom_openapi() -> dict[str, object]:
        if app.openapi_schema:
            return app.openapi_schema
        schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )
        components = schema.setdefault("components", {})
        schemas = components.setdefault("schemas", {})
        schemas["PredictByIdRequest"] = PredictByIdRequest.model_json_schema(
            ref_template="#/components/schemas/{model}"
        )
        app.openapi_schema = schema
        return schema

    app.openapi = custom_openapi  # type: ignore[method-assign]
    return app


app = create_app()
