import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any
from uuid import UUID

from sqlalchemy.exc import DBAPIError, OperationalError, SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from sse.config import (
    EVENT_BATCH_SIZE,
    MAX_STREAM_DURATION_SECONDS,
    POLL_INTERVAL_SECONDS,
    RETRY_DELAYS_SECONDS,
    TERMINAL_JOB_STATUSES,
)
from sse.connection_registry import ConnectionRegistry
from sse.encoder import encode_control, encode_event
from sse.repository import EventLogPollingRepository, PollSnapshot

logger = logging.getLogger(__name__)


class SSEStreamService:
    def __init__(
        self,
        repository: EventLogPollingRepository,
        connection_registry: ConnectionRegistry,
        *,
        poll_interval: float = POLL_INTERVAL_SECONDS,
        batch_size: int = EVENT_BATCH_SIZE,
        max_duration: float = MAX_STREAM_DURATION_SECONDS,
        retry_delays: tuple[float, ...] = RETRY_DELAYS_SECONDS,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        run_sync: Callable[..., Awaitable[Any]] = run_in_threadpool,
    ):
        self._repository = repository
        self._registry = connection_registry
        self._poll_interval = poll_interval
        self._batch_size = batch_size
        self._max_duration = max_duration
        self._retry_delays = retry_delays
        self._clock = clock
        self._sleep = sleep
        self._run_sync = run_sync

    async def stream(self, job_id: UUID, last_seen_id: int) -> AsyncIterator[str]:
        started_at = self._clock()
        cursor = last_seen_id

        try:
            while True:
                if self._clock() - started_at >= self._max_duration:
                    yield encode_control(
                        "STREAM_RECONNECT",
                        job_id,
                        reason="MAX_DURATION",
                    )
                    return

                snapshot = await self._fetch_with_retry(job_id, cursor)
                if snapshot.job_status is None:
                    yield encode_control("STREAM_ERROR", job_id, code="JOB_NOT_FOUND")
                    return

                for event in snapshot.events:
                    yield encode_event(event)
                    cursor = event.event_id

                if (
                    snapshot.job_status in TERMINAL_JOB_STATUSES
                    and len(snapshot.events) < self._batch_size
                ):
                    yield encode_control(
                        "STREAM_END",
                        job_id,
                        status=snapshot.job_status,
                    )
                    return

                if len(snapshot.events) >= self._batch_size:
                    continue

                remaining = self._max_duration - (self._clock() - started_at)
                await self._sleep(min(self._poll_interval, max(0.0, remaining)))
        except asyncio.CancelledError:
            raise
        except SQLAlchemyError:
            logger.exception("SSE polling failed for job %s", job_id)
            yield encode_control("STREAM_ERROR", job_id, code="DATABASE_UNAVAILABLE")
        except Exception:
            logger.exception("SSE stream failed for job %s", job_id)
            yield encode_control("STREAM_ERROR", job_id, code="INTERNAL_ERROR")
        finally:
            await self._registry.release()

    async def _fetch_with_retry(
        self,
        job_id: UUID,
        last_seen_id: int,
    ) -> PollSnapshot:
        attempt = 0
        while True:
            try:
                return await self._run_sync(
                    self._repository.fetch_snapshot,
                    job_id,
                    last_seen_id,
                    self._batch_size,
                )
            except (OperationalError, DBAPIError) as exc:
                if not self._is_transient(exc) or attempt >= len(self._retry_delays):
                    raise
                delay = self._retry_delays[attempt]
                attempt += 1
                await self._sleep(delay)

    @staticmethod
    def _is_transient(exc: DBAPIError) -> bool:
        return isinstance(exc, OperationalError) or bool(exc.connection_invalidated)

