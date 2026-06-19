import logging
from uuid import UUID
from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, status, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database import get_db
from jobs.schemas import JobCreateRequest, JobResponse, RefinementRequest
from jobs.service import (
    JobService,
    RefinementConflictError,
    RefinementContextTooLargeError,
    RefinementNotFoundError,
)
from storage.interface import StorageService
from storage.local import LocalStorageService
from limiter import limiter
from sse.router import get_stream_token_service
from sse.security import StreamTokenService
from orchestrator.service import JobOrchestratorService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])

# Storage Service 의존성 주입 제너레이터
def get_storage_service() -> StorageService:
    return LocalStorageService()

def get_orchestrator_service(request: Request) -> JobOrchestratorService:
    return request.app.state.orchestrator_service


def _job_response(job, token_service: StreamTokenService) -> JobResponse:
    return JobResponse(
        id=job.id,
        parent_job_id=job.parent_job_id,
        prompt=job.prompt,
        status=job.status,
        action_plan=job.action_plan,
        created_at=job.created_at,
        updated_at=job.updated_at,
        stream_url=f"/api/v1/jobs/{job.id}/stream",
        stream_token=token_service.create_token(job.id),
    )

@router.post(
    "",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="자연어 기반 설계 Job 생성"
)
@limiter.limit("10/minute")
def create_job(
    request_body: JobCreateRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    token_service: StreamTokenService = Depends(get_stream_token_service),
    orchestrator: JobOrchestratorService = Depends(get_orchestrator_service),
):
    """
    사용자 자연어 요구사항을 바탕으로 Job을 생성하고, 로컬 디렉토리 Workspace를 초기화한 후
    백그라운드 오케스트레이터를 기동합니다.
    """
    job_service = JobService(db, storage_service)
    
    # 1. Job 엔티티 및 스토리지 공간 생성
    job = job_service.create_job(prompt=request_body.prompt)
    
    # 2. 백그라운드 오케스트레이터 태스크 등록
    background_tasks.add_task(orchestrator.run, job.id)
    
    return _job_response(job, token_service)


@router.post(
    "/{previous_job_id}/refine",
    response_model=JobResponse,
    status_code=status.HTTP_201_CREATED,
    summary="완료 Job 기반 반복 수정",
)
def refine_job(
    previous_job_id: UUID,
    request_body: RefinementRequest,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service),
    token_service: StreamTokenService = Depends(get_stream_token_service),
    orchestrator: JobOrchestratorService = Depends(get_orchestrator_service),
):
    job_service = JobService(db, storage_service)
    try:
        job = job_service.create_refinement_job(previous_job_id, request_body.prompt)
    except RefinementNotFoundError as exc:
        raise HTTPException(status_code=404, detail={"status": "error", "code": "PARENT_NOT_FOUND", "message": str(exc)}) from exc
    except RefinementConflictError as exc:
        raise HTTPException(status_code=409, detail={"status": "error", "code": "REFINEMENT_CONFLICT", "message": str(exc)}) from exc
    except RefinementContextTooLargeError as exc:
        raise HTTPException(status_code=413, detail={"status": "error", "code": "CONTEXT_TOO_LARGE", "message": str(exc)}) from exc

    background_tasks.add_task(orchestrator.run, job.id)
    return _job_response(job, token_service)

@router.get(
    "/{job_id}/artifacts/{filename:path}",
    summary="최종 결과 아티팩트 다운로드"
)
def download_artifact(
    job_id: UUID,
    filename: str,
    db: Session = Depends(get_db),
    storage_service: StorageService = Depends(get_storage_service)
):
    """
    성공한 Job에 한하여 생성된 최종 아티팩트(.stl, .png 등) 파일을 안전하게 다운로드합니다.
    - Directory Traversal 침투 방어가 강제 적용됩니다.
    """
    job_service = JobService(db, storage_service)
    
    # 1. DB에서 Job 유효성 검증
    job = job_service.get_job(job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "code": "NOT_FOUND",
                "message": f"Job {job_id} not found."
            }
        )
    
    # 2. Job 상태 검증 (실패한 Job에 대해서는 다운로드 제공 거부)
    if job.status == "FAILED":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "status": "error",
                "code": "BAD_REQUEST",
                "message": f"Job {job_id} has failed. Cannot retrieve artifacts."
            }
        )
        
    # 3. 물리 파일 검증 및 다운로드 스트리밍
    try:
        # 파일 존재 여부 검사 (이 과정에서 Path Traversal도 내부에서 검증됨)
        if not storage_service.check_artifact_exists(job_id, filename):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={
                    "status": "error",
                    "code": "NOT_FOUND",
                    "message": f"Artifact {filename} not found for Job {job_id}."
                }
            )
            
        file_path = storage_service.get_artifact_path(job_id, filename)
        
        # 파일 미디어 타입 정의 생략하고 파일명을 명시하여 다운로드 처리
        return FileResponse(
            path=str(file_path),
            filename=filename,
            media_type="application/octet-stream"
        )
        
    except PermissionError as e:
        # Directory Traversal 시도 등으로 예외가 발생한 경우 403 반환
        logger.warning(f"Security Alert: Directory Traversal attempt detected on job {job_id}. Path: {filename}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "status": "error",
                "code": "FORBIDDEN_ACCESS",
                "message": "Access denied. Path traversal detected."
            }
        )
    except FileNotFoundError:
        # 혹여나 내부 처리 중 파일이 소실된 경우 404 반환
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "status": "error",
                "code": "NOT_FOUND",
                "message": f"Artifact {filename} not found for Job {job_id}."
            }
        )
