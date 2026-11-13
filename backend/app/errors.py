"""Structured error types and FastAPI exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ErrorEnvelope(BaseModel):
    """Consistent error envelope returned by all API endpoints."""

    code: str
    message: str
    details: dict[str, Any] | list[Any] | None = None


class AppError(Exception):
    """Base application error carrying HTTP status and structured code."""

    status_code: int = 400
    code: str = "APP_ERROR"

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status_code: int | None = None,
        details: dict[str, Any] | list[Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code
        self.details = details


class ModelNotTrainedError(AppError):
    status_code = 503
    code = "MODEL_NOT_TRAINED"


class NoDatasetError(AppError):
    status_code = 404
    code = "NO_DATASET"


class CascadeNotFoundError(AppError):
    status_code = 404
    code = "CASCADE_NOT_FOUND"


class InvalidInputError(AppError):
    status_code = 400
    code = "INVALID_INPUT"


class PayloadTooLargeError(AppError):
    status_code = 413
    code = "PAYLOAD_TOO_LARGE"


class UnsupportedMediaTypeError(AppError):
    status_code = 415
    code = "UNSUPPORTED_MEDIA_TYPE"


class FutureEventLeakageError(AppError):
    status_code = 500
    code = "FUTURE_EVENT_LEAKAGE"


def _request_id_from(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def register_exception_handlers(app: FastAPI) -> None:
    """Register exception handlers that never leak raw stack traces."""

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        logger.warning(
            "AppError request_id=%s code=%s message=%s",
            _request_id_from(request),
            exc.code,
            exc.message,
        )
        envelope = ErrorEnvelope(code=exc.code, message=exc.message, details=exc.details)
        return JSONResponse(status_code=exc.status_code, content=envelope.model_dump())

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "RequestValidationError request_id=%s errors=%s",
            _request_id_from(request),
            len(exc.errors()),
        )
        safe_errors = [
            {
                "loc": list(err.get("loc", ())),
                "msg": str(err.get("msg", "")),
                "type": err.get("type"),
            }
            for err in exc.errors()
        ]
        envelope = ErrorEnvelope(
            code="REQUEST_VALIDATION_ERROR",
            message="Request validation failed.",
            details=safe_errors,
        )
        return JSONResponse(status_code=422, content=envelope.model_dump())

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error request_id=%s type=%s",
            _request_id_from(request),
            type(exc).__name__,
        )
        envelope = ErrorEnvelope(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected internal error occurred.",
            details=None,
        )
        return JSONResponse(status_code=500, content=envelope.model_dump())
