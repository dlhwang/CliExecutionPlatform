from collections.abc import Callable
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from database import SessionLocal
from sse.config import STREAM_TOKEN_HEADER
from sse.connection_registry import ConnectionRegistry
from sse.repository import EventLogPollingRepository
from sse.security import StreamTokenService
from sse.service import SSEStreamService

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])
_connection_registry = ConnectionRegistry()


def get_sse_session_factory() -> Callable[[], Session]:
    return SessionLocal


def get_connection_registry() -> ConnectionRegistry:
    return _connection_registry


def get_stream_token_service() -> StreamTokenService:
    return StreamTokenService.from_environment()


def _error_detail(code: str, message: str) -> dict[str, str]:
    return {"status": "error", "code": code, "message": message}


def _parse_last_event_id(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@router.get("/{job_id}/stream", summary="Job SSE event stream")
async def stream_job_events(
    job_id: UUID,
    stream_token: str | None = Header(default=None, alias=STREAM_TOKEN_HEADER),
    last_event_id: str | None = Header(default=None, alias="Last-Event-ID"),
    session_factory: Callable[[], Session] = Depends(get_sse_session_factory),
    registry: ConnectionRegistry = Depends(get_connection_registry),
    token_service: StreamTokenService = Depends(get_stream_token_service),
):
    repository = EventLogPollingRepository(session_factory)

    try:
        exists = await run_in_threadpool(repository.job_exists, job_id)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail("DATABASE_UNAVAILABLE", "Database is unavailable."),
        ) from exc

    if not exists:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_error_detail("NOT_FOUND", f"Job {job_id} not found."),
        )

    if not token_service.verify_token(job_id, stream_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=_error_detail("INVALID_STREAM_TOKEN", "Stream access denied."),
        )

    candidate = _parse_last_event_id(last_event_id)
    try:
        cursor = await run_in_threadpool(repository.resolve_cursor, job_id, candidate)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail("DATABASE_UNAVAILABLE", "Database is unavailable."),
        ) from exc

    if not await registry.try_acquire():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_error_detail(
                "STREAM_CAPACITY_EXCEEDED",
                "SSE connection capacity has been reached.",
            ),
        )

    try:
        service = SSEStreamService(repository, registry)
        return StreamingResponse(
            service.stream(job_id, cursor),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
    except Exception:
        await registry.release()
        raise

