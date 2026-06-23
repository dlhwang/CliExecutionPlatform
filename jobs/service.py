import mimetypes
from pathlib import PurePosixPath, Path
from sqlalchemy.orm import Session
from uuid import UUID
from typing import Optional, List
from jobs.models import Job, EventLog, Artifact
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


class ArtifactNotFoundError(Exception):
    pass


class ArtifactPermissionError(Exception):
    pass


class ArtifactService:
    def __init__(self, db: Session, storage_service: StorageService):
        self.db = db
        self.storage_service = storage_service

    def register_artifact(self, job_id: UUID, relative_path: str) -> Artifact:
        # 1. 논리 검증
        if not relative_path or not relative_path.strip():
            raise ArtifactPermissionError("Access Denied: Empty path is not allowed.")
        if "\\" in relative_path:
            raise ArtifactPermissionError("Access Denied: Windows backslashes are not allowed.")
        
        posix_path = PurePosixPath(relative_path)
        if posix_path.is_absolute():
            raise ArtifactPermissionError("Access Denied: Absolute paths are not allowed.")
            
        segments = relative_path.replace("\\", "/").split("/")
        if any(s in (".", "..") or not s for s in segments):
            raise ArtifactPermissionError("Access Denied: Invalid path segments (., .. or empty) are not allowed.")
                
        # 2. 물리 검증
        base_dir = getattr(self.storage_service, "base_dir", Path(__file__).parent.parent.resolve() / ".workspaces")
        base_job_dir = (base_dir / "jobs" / str(job_id)).resolve()
        target_path = (base_job_dir / relative_path).resolve()
        
        if not target_path.is_relative_to(base_job_dir):
            raise ArtifactPermissionError("Access Denied: Path traversal attempt detected.")

        # 3. 메타데이터 세팅 및 저장
        filename = posix_path.name  # basename에서만 파생
        content_type, _ = mimetypes.guess_type(filename)
        if not content_type:
            content_type = "application/octet-stream"

        artifact = Artifact(
            job_id=job_id,
            relative_path=relative_path,
            filename=filename,
            content_type=content_type
        )
        self.db.add(artifact)
        self.db.flush()  # DB ID 생성을 위해 flush
        return artifact

    def get_artifact_for_download(self, artifact_id: UUID) -> tuple[Path, str, str]:
        # 1. DB 조회
        artifact = self.db.query(Artifact).filter(Artifact.id == artifact_id).first()
        if not artifact:
            raise ArtifactNotFoundError("Artifact not found in database.")

        # 2. 논리 검증
        relative_path = artifact.relative_path
        if not relative_path or not relative_path.strip():
            raise ArtifactPermissionError("Access Denied: Empty path is not allowed.")
        if "\\" in relative_path:
            raise ArtifactPermissionError("Access Denied: Windows backslashes are not allowed.")
        
        posix_path = PurePosixPath(relative_path)
        if posix_path.is_absolute():
            raise ArtifactPermissionError("Access Denied: Absolute paths are not allowed.")
            
        segments = relative_path.replace("\\", "/").split("/")
        if any(s in (".", "..") or not s for s in segments):
            raise ArtifactPermissionError("Access Denied: Invalid path segments (., .. or empty) are not allowed.")

        # 3. 물리 검증
        base_dir = getattr(self.storage_service, "base_dir", Path(__file__).parent.parent.resolve() / ".workspaces")
        base_job_dir = (base_dir / "jobs" / str(artifact.job_id)).resolve()
        target_path = (base_job_dir / relative_path).resolve()

        if not target_path.is_relative_to(base_job_dir):
            raise ArtifactPermissionError("Access Denied: Path traversal attempt detected.")

        # 4. 파일 존재 여부 및 일반 파일 여부 확인
        if not target_path.exists() or not target_path.is_file():
            raise ArtifactNotFoundError("Physical file not found or is not a regular file.")

        return target_path, artifact.content_type, artifact.filename

