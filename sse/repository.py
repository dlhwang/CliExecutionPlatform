from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy.orm import Session

from jobs.models import EventLog, Job
from sse.config import EVENT_BATCH_SIZE


@dataclass(frozen=True)
class EventRecord:
    event_id: int
    job_id: UUID
    event_type: str
    message: str
    created_at: datetime


@dataclass(frozen=True)
class PollSnapshot:
    events: tuple[EventRecord, ...]
    job_status: str | None


class EventLogPollingRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def job_exists(self, job_id: UUID) -> bool:
        db = self._session_factory()
        try:
            return db.query(Job.id).filter(Job.id == job_id).first() is not None
        finally:
            db.close()

    def resolve_cursor(self, job_id: UUID, candidate: int | None) -> int:
        if candidate is None or candidate <= 0:
            return 0

        db = self._session_factory()
        try:
            event_exists = (
                db.query(EventLog.id)
                .filter(EventLog.job_id == job_id, EventLog.id == candidate)
                .first()
                is not None
            )
            return candidate if event_exists else 0
        finally:
            db.close()

    def fetch_snapshot(
        self,
        job_id: UUID,
        last_seen_id: int,
        limit: int = EVENT_BATCH_SIZE,
    ) -> PollSnapshot:
        db = self._session_factory()
        try:
            job_status_row = db.query(Job.status).filter(Job.id == job_id).first()
            if job_status_row is None:
                return PollSnapshot(events=(), job_status=None)

            rows = (
                db.query(EventLog)
                .filter(EventLog.job_id == job_id, EventLog.id > last_seen_id)
                .order_by(EventLog.id.asc())
                .limit(limit)
                .all()
            )
            events = tuple(
                EventRecord(
                    event_id=row.id,
                    job_id=row.job_id,
                    event_type=row.event_type,
                    message=row.message,
                    created_at=row.created_at,
                )
                for row in rows
            )
            return PollSnapshot(events=events, job_status=job_status_row[0])
        finally:
            db.close()

