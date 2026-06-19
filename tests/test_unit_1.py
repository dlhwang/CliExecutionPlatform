import uuid
import pytest
from pathlib import Path
from unittest.mock import patch
from fastapi import status
from sqlalchemy.orm import Session
from uuid6 import uuid7

from jobs.models import Job
from storage.local import LocalStorageService

# -------------------------------------------------------------------
# 1. Job 생성 및 Workspace 생성 검증
# -------------------------------------------------------------------
def test_job_creation(client, db_session: Session, test_storage: LocalStorageService):
    """
    POST /api/v1/jobs 요청 시 Job이 CREATED 상태로 DB에 올바르게 삽입되고,
    물리 로컬 작업 공간 디렉토리가 생성되는지 검증합니다. (Story S-1)
    """
    prompt_text = "샤오미 워치 S4 충전 도킹스테이션 설계도를 만들어줘"
    
    # API 요청 전송
    response = client.post(
        "/api/v1/jobs",
        json={"prompt": prompt_text}
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    
    # 1. job_id 발급 규격 검증 (UUIDv7 포맷 여부)
    job_id_str = data.get("id")
    assert job_id_str is not None
    job_uuid = uuid.UUID(job_id_str)
    # UUIDv7인 경우 4비트 버전 필드가 7(0111)이어야 함
    assert job_uuid.version == 7
    
    # 2. 데이터베이스 상태 CREATED 검증
    db_job = db_session.query(Job).filter(Job.id == job_uuid).first()
    assert db_job is not None
    assert db_job.prompt == prompt_text
    assert db_job.status == "CREATED"
    
    # 3. 호스트 파일시스템 상에 .workspaces 디렉토리가 생성되었는지 검증
    jobs_dir = test_storage.base_dir / "jobs" / job_id_str
    artifacts_dir = test_storage.base_dir / "artifacts" / job_id_str
    
    assert jobs_dir.exists() and jobs_dir.is_dir()
    assert artifacts_dir.exists() and artifacts_dir.is_dir()


# -------------------------------------------------------------------
# 2. 경로 탈출(Directory Traversal) 공격 방어 검증
# -------------------------------------------------------------------
def test_directory_traversal_protection(client, db_session: Session, test_storage: LocalStorageService):
    """
    비인가 경로 탈출(../) 요청 시 HTTP 403 Forbidden 및 에러 응답을 반환하는지와
    LocalStorageService 레벨에서 PermissionError를 던지는지 검증합니다. (Story S-4)
    """
    # 임의의 완료된 Job 등록
    job_id = uuid7()
    job = Job(
        id=job_id,
        prompt="Test prompt",
        status="COMPLETED"
    )
    db_session.add(job)
    db_session.commit()
    
    # 물리 workspace 생성
    test_storage.create_workspace(job_id)
    
    # 1. API 레벨 검증:
    # HTTP 클라이언트(httpx) 및 Starlette 라우팅의 자체 URL 경로 정규화(/../ 해석 및 404 차단)를 우회하여,
    # LocalStorageService가 PermissionError를 반환할 때 라우터와 전역 핸들러가 403 Forbidden을
    # 정상적으로 출력하고 포맷팅하는지 검증하기 위해 mock.patch를 사용합니다.
    with patch.object(LocalStorageService, "check_artifact_exists", side_effect=PermissionError("Access Denied")):
        response = client.get(f"/api/v1/jobs/{job_id}/artifacts/malicious_file.stl")
        
    assert response.status_code == status.HTTP_403_FORBIDDEN
    data = response.json()
    assert data["detail"]["code"] == "FORBIDDEN_ACCESS"
    assert "Access denied. Path traversal detected." in data["detail"]["message"]

    # 2. Service/Storage 레벨 검증:
    # 허용 영역 밖의 경로 입력 주입 시 PermissionError 예외가 내부에서 정상 트리거되는지 검증
    with pytest.raises(PermissionError) as exc_info:
        test_storage.get_artifact_path(job_id, "../test.txt")
    assert "Access Denied: Path traversal attempt detected." in str(exc_info.value)


# -------------------------------------------------------------------
# 3. API 속도 제한 작동 검증 (Rate Limiting)
# -------------------------------------------------------------------
def test_rate_limiting(client):
    """
    동일 IP에서 단시간 내 다중 요청 시, 분당 10회 제한 정책에 의해
    결국 HTTP 429 Too Many Requests가 트리거되는지 검증합니다.
    """
    prompt_text = "속도제한 테스트용 프롬프트"
    
    # 타 테스트에 의해 limiter 누적치가 다를 수 있으므로 최대 12회 루프를 돌면서 
    # 429 에러가 정상적으로 유발 및 핸들링되는지 확인합니다.
    rate_limited = False
    for _ in range(12):
        response = client.post(
            "/api/v1/jobs",
            json={"prompt": prompt_text}
        )
        if response.status_code == status.HTTP_429_TOO_MANY_REQUESTS:
            rate_limited = True
            data = response.json()
            assert data["detail"]["code"] == "RATE_LIMIT_EXCEEDED"
            break
        else:
            assert response.status_code == status.HTTP_201_CREATED
            
    assert rate_limited, "Rate limit should have been triggered within 12 requests."


# -------------------------------------------------------------------
# 4. 아티팩트 스트리밍 다운로드 검증
# -------------------------------------------------------------------
def test_artifact_download(client, db_session: Session, test_storage: LocalStorageService):
    """
    성공(COMPLETED) 상태인 Job의 아티팩트를 정상적으로 다운로드하며,
    파일 바이트 내용이 원본과 완벽히 일치하는지 검증합니다. (Story S-4)
    """
    # 1. 완료 상태의 Job 데이터베이스 레코드 준비
    job_id = uuid7()
    job = Job(
        id=job_id,
        prompt="아티팩트 테스트 프롬프트",
        status="COMPLETED"
    )
    db_session.add(job)
    db_session.commit()
    
    # 2. 물리 Workspace 디렉토리 생성 및 아티팩트 파일 저장
    test_storage.create_workspace(job_id)
    
    artifact_content = b"STL binary content data..."
    filename = "model.stl"
    
    # 임시 폴더에 파일 쓰기 후 영구 아티팩트 폴더로 복사
    test_storage.write_file(job_id, filename, artifact_content)
    test_storage.save_artifact(job_id, filename)
    
    # 3. GET 다운로드 API 호출 및 응답 바이트 검증
    response = client.get(f"/api/v1/jobs/{job_id}/artifacts/{filename}")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.content == artifact_content
    
    # 4. 실패(FAILED) 상태인 Job인 경우 아티팩트 다운로드가 거부되는지 검증
    failed_job_id = uuid7()
    failed_job = Job(
        id=failed_job_id,
        prompt="실패 테스트 프롬프트",
        status="FAILED"
    )
    db_session.add(failed_job)
    db_session.commit()
    
    test_storage.create_workspace(failed_job_id)
    test_storage.write_file(failed_job_id, filename, artifact_content)
    test_storage.save_artifact(failed_job_id, filename)
    
    failed_response = client.get(f"/api/v1/jobs/{failed_job_id}/artifacts/{filename}")
    assert failed_response.status_code == status.HTTP_400_BAD_REQUEST
    failed_data = failed_response.json()
    assert failed_data["detail"]["code"] == "BAD_REQUEST"
