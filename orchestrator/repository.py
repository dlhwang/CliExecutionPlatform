from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from jobs.models import EventLog, Job


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    parent_job_id: UUID | None
    prompt: str
    status: str


class OrchestratorRepository:
    def __init__(self, session_factory: Callable[[], Session]):
        self._session_factory = session_factory

    def get_job(self, job_id: UUID) -> JobRecord | None:
        db = self._session_factory()
        try:
            job = db.query(Job).filter(Job.id == job_id).first()
            if job is None:
                return None
            return JobRecord(job.id, job.parent_job_id, job.prompt, job.status)
        finally:
            db.close()

    def transition(
        self,
        job_id: UUID,
        expected_statuses: tuple[str, ...],
        target_status: str,
        event_code: str,
        message: str,
    ) -> bool:
        db = self._session_factory()
        try:
            updated = (
                db.query(Job)
                .filter(Job.id == job_id, Job.status.in_(expected_statuses))
                .update(
                    {Job.status: target_status, Job.updated_at: func.now()},
                    synchronize_session=False,
                )
            )
            if updated != 1:
                db.rollback()
                return False
            db.add(EventLog(job_id=job_id, event_type="SYSTEM_EVENT", message=f"[{event_code}] {message}"))
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def append_event(self, job_id: UUID, event_code: str, message: str) -> None:
        db = self._session_factory()
        try:
            db.add(EventLog(job_id=job_id, event_type="SYSTEM_EVENT", message=f"[{event_code}] {message}"))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def save_action_plan(self, job_id: UUID, actions) -> None:
        serialized = [action.model_dump(mode="json") for action in actions]
        db = self._session_factory()
        try:
            updated = (
                db.query(Job)
                .filter(Job.id == job_id, Job.status == "RUNNING")
                .update({Job.action_plan: serialized, Job.updated_at: func.now()}, synchronize_session=False)
            )
            if updated != 1:
                raise RuntimeError("Job is not RUNNING while saving action plan.")
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def recover_stale(self, cutoff: datetime) -> int:
        db = self._session_factory()
        recovered = 0
        try:
            job_ids = [
                row[0]
                for row in db.query(Job.id)
                .filter(Job.status == "RUNNING", Job.updated_at < cutoff)
                .all()
            ]
        finally:
            db.close()

        for job_id in job_ids:
            if self._recover_one(job_id, cutoff):
                recovered += 1
        return recovered

    def _recover_one(self, job_id: UUID, cutoff: datetime) -> bool:
        db = self._session_factory()
        try:
            updated = (
                db.query(Job)
                .filter(Job.id == job_id, Job.status == "RUNNING", Job.updated_at < cutoff)
                .update(
                    {Job.status: "FAILED", Job.updated_at: func.now()},
                    synchronize_session=False,
                )
            )
            if updated != 1:
                db.rollback()
                return False
            db.add(
                EventLog(
                    job_id=job_id,
                    event_type="SYSTEM_EVENT",
                    message="[STALE_JOB_RECOVERED] Job failed after interrupted process recovery.",
                )
            )
            db.commit()
            return True
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

