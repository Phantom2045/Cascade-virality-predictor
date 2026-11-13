"""FastAPI dependency helpers and upload guards."""

from __future__ import annotations

from fastapi import Request, UploadFile

from app.errors import PayloadTooLargeError, UnsupportedMediaTypeError
from app.services.model_store import AppStore

_ALLOWED_CSV_TYPES = {
    "text/csv",
    "application/csv",
    "text/plain",
    "application/vnd.ms-excel",
    "application/octet-stream",
    "",
}


def get_store(request: Request) -> AppStore:
    """Return the startup-cached AppStore instance from FastAPI app state."""
    store: AppStore = request.app.state.store
    return store


async def read_validated_csv_upload(file: UploadFile, max_bytes: int) -> bytes:
    """Enforce filename extension, content-type, and max byte size on uploaded CSV."""
    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".csv"):
        raise UnsupportedMediaTypeError(
            "Only .csv files are supported.",
            details={"filename": file.filename},
        )

    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if content_type not in _ALLOWED_CSV_TYPES:
        raise UnsupportedMediaTypeError(
            f"Unsupported content-type '{file.content_type}'. Upload a UTF-8 CSV file.",
            details={"content_type": file.content_type},
        )

    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(65536)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise PayloadTooLargeError(
                f"Uploaded file exceeds the {max_bytes // (1024 * 1024)} MB limit.",
                details={"max_bytes": max_bytes},
            )
        chunks.append(chunk)

    return b"".join(chunks)
