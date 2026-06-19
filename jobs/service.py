from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List
from jobs.models import Job, EventLog
from storage.interface import StorageService

MAX_REFINEMENT_CONTEXT_BYTES = 5 * 1024 * 1024
REFINEMENT_FILES = ("model.scad", "design-spec.md")


class RefinementNotFoundError(RuntimeError):
    pass


class RefinementConflictError(RuntimeError):
    pass


class RefinementContextTooLargeError(RuntimeError):
    pass

class JobService:
    """
    Job 생성, Workspace 초기화, 로그 적재 및 상태 조회를 처리하는 비즈니스 서비스 클래스.
    """
    def __init__(self, db: Session, storage_service: StorageService):
        self.db = db
        self.storage_service = storage_service

    def create_job(self, prompt: str, parent_job_id: UUID | None = None) -> Job:
        """
        새로운 Job을 생성하고, 전용 Workspace 물리 디렉토리를 생성하며, 최초 시스템 로그를 등록합니다.
        """
        # 1. Job 엔티티 생성 및 DB 저장
        job = Job(
            prompt=prompt,
            status="CREATED",
            parent_job_id=parent_job_id,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(job)

        # 2. 물리 저장 공간(Workspace) 초기화
        self.storage_service.create_workspace(job.id)

        # 3. 최초 시스템 이벤트 로그 기록
        log = EventLog(
            job_id=job.id,
            event_type="SYSTEM",
            message="Job created and workspace initialized."
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(job)

        return job

    def create_refinement_job(self, parent_job_id: UUID, prompt: str) -> Job:
        parent = self.get_job(parent_job_id)
        if parent is None:
            raise RefinementNotFoundError("Parent Job was not found.")
        if parent.status != "COMPLETED":
            raise RefinementConflictError("Parent Job must be COMPLETED.")

        total_size = 0
        for filename in REFINEMENT_FILES:
            if not self.storage_service.workspace_file_exists(parent_job_id, filename):
                raise RefinementConflictError(f"Required parent file is missing: {filename}")
            total_size += self.storage_service.workspace_file_size(parent_job_id, filename)
        if total_size > MAX_REFINEMENT_CONTEXT_BYTES:
            raise RefinementContextTooLargeError("Refinement context exceeds 5MB.")

        return self.create_job(prompt=prompt, parent_job_id=parent_job_id)

    def get_job(self, job_id: UUID) -> Optional[Job]:
        """
        특정 Job ID를 가진 Job 엔티티를 조회합니다.
        """
        return self.db.query(Job).filter(Job.id == job_id).first()

    def get_event_logs(self, job_id: UUID) -> List[EventLog]:
        """
        특정 Job과 연관된 전체 이벤트 로그 목록을 ID 오름차순(시간순)으로 조회합니다.
        """
        return self.db.query(EventLog).filter(EventLog.job_id == job_id).order_by(EventLog.id).all()
