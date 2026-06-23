# Code Generation Summary - R-16 (보안 아티팩트 다운로드 엔드포인트)

본 문서는 R-16 보안 다운로드 엔드포인트 구현 내역 및 보안 검증 설계의 요약본입니다.

## 1. 구현 세부 내역

### 1) DB 스키마 추가 (`jobs/models.py`)
- `Artifact` 테이블 ORM 모델 정의:
  - `id`: UUID (시간 정렬이 가능한 uuid7 기본값)
  - `job_id`: UUID (ForeignKey "jobs.id", CASCADE)
  - `relative_path`: String(500) (상대경로 검증 필터 완료)
  - `filename`: String(255) (relative_path의 basename 파생값)
  - `content_type`: String(100) (다운로드 시의 미디어 타입)
  - `created_at`: DateTime (func.now() KST 타임존 적용)
- `Job` 모델 내에 1:N 관계 매핑 (`artifacts`) 추가.

### 2) 서비스 계층 구현 (`jobs/service.py`)
- `ArtifactService` 구현:
  - `register_artifact(job_id, relative_path)`:
    - **논리적 검증**: 빈 경로, Windows 역슬래시(`\`), 절대경로 여부, 세그먼트 내 `.`, `..` 존재 여부 검사.
    - **물리적 검증**: `Path.resolve()` 정규화 후 `is_relative_to`로 `jobs/{job_id}` workspace root 내부에 위치하는지 이중 체크.
    - 파일 확장자에 근거한 `content_type` 추정 및 `filename` basename 파생값으로 설정해 DB에 영속화.
  - `get_artifact_for_download(artifact_id)`:
    - 아티팩트 ID로 DB 조회.
    - 다운로드 시점 경로 재검증(Windows 역슬래시, 빈 경로, `.`, `..` 세그먼트, 절대경로 검사).
    - `jobs/{job_id}` workspace root 디렉토리를 샌드박스로 확보하여 `Path.resolve()` 정규화 후 `is_relative_to` 물리 검증 (prefix-bypass 및 symlink escape 차단).
    - 파일의 실제 존재 및 일반 파일 여부(`is_file()`) 검사.

### 3) 오케스트레이터 연동 및 Best-Effort Cleanup (`orchestrator/actions.py`)
- `ActionExecutor.execute_attempt` 내에서 `save_artifact` 호출 성공 후 `ArtifactService.register_artifact`를 호출하여 DB 메타데이터를 저장.
- DB 트랜잭션(`commit/rollback`)으로 묶어 일관성 보장.
- 파일 복사 이후 DB 등록/검증 중 예외 발생 시, 이미 복사된 아티팩트 파일을 지워주는 예외 안전망(Best-Effort Cleanup) 구현.

### 4) API 라우터 구현 및 등록 (`jobs/router.py`, `main.py`)
- `router_artifacts = APIRouter(prefix="/api/v1/artifacts")` 추가.
- `GET /api/v1/artifacts/{artifact_id}/download` 엔드포인트 구현:
  - `ArtifactNotFoundError` -> HTTP 404 Not Found
  - `ArtifactPermissionError` -> HTTP 403 Forbidden
  - 에러 메시지에 절대 서버 경로가 포함되지 않도록 마스킹 처리.
  - 성공 시 `FileResponse`에 파일 경로, `Content-Type`, `Content-Disposition` 다운로드 filename 설정하여 반환.

## 2. 검증 결과 요약
- `tests/test_unit_2.py`에 다음 보안 및 기능 시나리오 테스트 케이스 13개 추가 완료:
  - 정상 경로 등록 성공 및 비정상(절대경로, traversal, Windows 역슬래시) 등록 시 차단.
  - 정상 다운로드 성공(Content-Type 및 파일명 확인).
  - 404 반환 경계 조건 (존재하지 않는 ID, 파일 누락, 디렉터리 요청 시).
  - 403 차단 경계 조건 (traversal, 절대경로, prefix-bypass, symlink escape 시도 시).
  - 에러 메시지 내 절대경로 유출 차단 검증.
- 전체 92개 테스트 구동 결과 100% 통과 확인.
