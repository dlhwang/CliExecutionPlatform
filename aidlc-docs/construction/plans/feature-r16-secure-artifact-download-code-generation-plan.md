# Code Generation Plan - R-16 (보안 아티팩트 다운로드 엔드포인트)

본 계획서는 R-16 아티팩트 다운로드 API 및 보안 검증 기능 구현을 위한 단일 진실 공급원(Single Source of Truth)입니다.

## 1. Unit Context & Details

- **대상 영역**: Database Models, Storage/Service Layer, API Router, Unit/Integration/Security Tests
- **목적**: 
  - 생성된 산출물 파일을 다운로드할 때 물리적인 경로나 파일명을 클라이언트로부터 받지 않고 고유 `artifact_id`만을 통해 안전하게 다운로드받을 수 있는 엔드포인트 구축.
  - 아티팩트 등록 시점과 다운로드 시점 모두 상호 독립적으로 `PurePosixPath` 기반 논리 검증 및 `Path.resolve()` 물리 경로 검증을 수행하여 탈출 방어(Path Traversal, Absolute Path, Prefix-Bypass, Symlink Escape) 적용.
  - 권한/소유권 인가 검사 확장성을 고려하여 라우터가 아닌 `ArtifactService` 내부에서 다운로드 결정 및 경로 검증 처리를 은닉화.
  - 실패 시 에러 응답에 서버 절대 경로가 유출되지 않도록 철저한 통제 적용.

---

## 2. Code Generation Checklists

- [x] **Step 1: DB 스키마에 Artifact 모델 추가**
  - 파일 경로: [jobs/models.py](file:///d:/workspace/CLI-Execution-Platform/jobs/models.py) [MODIFY]
  - 구현 내용:
    - 아티팩트 메타데이터를 저장하기 위한 `Artifact` ORM 클래스 정의.
    - 필드 구성:
      - `id`: UUID (기본값 uuid7)
      - `job_id`: UUID (ForeignKey "jobs.id", ondelete="CASCADE")
      - `relative_path`: String(500) (Job workspace root 기준 상대 경로)
      - `filename`: String(255) (relative_path의 basename에서 파생된 파일명)
      - `content_type`: String(100) (파일 다운로드 시 Content-Type 헤더 정보)
      - `created_at`: DateTime(timezone=True) (서버 기본 func.now() 설정)
    - `Job` 모델 내에 `artifacts` 1:N relationship 매핑 추가.

- [x] **Step 2: ArtifactService 및 전용 예외 정의**
  - 파일 경로: [jobs/service.py](file:///d:/workspace/CLI-Execution-Platform/jobs/service.py) [MODIFY]
  - 구현 내용:
    - 서비스 내부에서 사용할 예외 클래스 정의:
      - `ArtifactNotFoundError(Exception)`: DB 메타데이터가 존재하지 않거나, 물리 파일이 없거나 디렉터리 등 일반 파일이 아닐 때 발생.
      - `ArtifactPermissionError(Exception)`: 절대경로, traversal(..), prefix-bypass 등의 침입 탐지 시 발생.
    - `ArtifactService` 클래스 정의:
      - 생성자: `__init__(self, db: Session, storage_service: StorageService)`
      - `register_artifact(self, job_id: UUID, relative_path: str) -> Artifact`
        - 등록 시점의 검증 (논리 검증 + 물리 검증):
          - **논리 검증**:
            - 빈 경로이거나 공백만 있는 경우 거부.
            - Windows 역슬래시(`\`)가 포함된 경우 거부.
            - `PurePosixPath`로 파싱 후 `is_absolute()` 검사하여 절대 경로 거부.
            - `parts` 중 `.`, `..` 혹은 빈 세그먼트(`""`)가 존재하면 거부.
          - **물리 검증**:
            - workspace root (`jobs/{job_id}`) 디렉토리를 샌드박스로 확보.
            - `Path.resolve()` 정규화 후 물리 파일이 workspace root 하위에 존재하는지 `is_relative_to` 검증.
        - `filename`은 `PurePosixPath(relative_path).name` (basename)에서만 파생하여 저장.
        - 파일 형식에 맞춰 `content_type` 추정 (`mimetypes.guess_type` 활용, 기본값 `application/octet-stream`).
        - `Artifact` 레코드 저장 및 반환.
      - `get_artifact_for_download(self, artifact_id: UUID) -> tuple[Path, str, str]`
        - `artifact_id`로 DB 조회, 없을 경우 `ArtifactNotFoundError` 발생.
        - 다운로드 시점의 검증 (논리 검증 + 물리 검증, 등록 시점 결과를 신뢰 경계로 간주하지 않음):
          - **논리 검증**:
            - `artifact.relative_path` 내 Windows 역슬래시(`\`), 빈 경로, `.`, `..` 세그먼트 혹은 절대경로 존재 시 즉시 차단 (`ArtifactPermissionError` 발생).
          - **물리 검증**:
            - 아티팩트의 `job_id`를 기반으로 `jobs/{job_id}` 디렉토리를 물리적 다운로드 샌드박스 기준(workspace root)으로 설정 (artifacts/가 아님).
            - 샌드박스 base 디렉토리와 타겟 파일 경로를 각각 `Path.resolve()` 정규화.
            - 타겟 경로가 샌드박스 내부인지 `target.is_relative_to(base)`로 확인하여 prefix-bypass 및 symlink escape 차단. 다르면 `ArtifactPermissionError` 발생.
        - 파일의 존재 및 일반 파일 여부(`is_file()`) 검사. 거짓일 경우 `ArtifactNotFoundError` 발생.
        - 모든 에러 메시지 구성 시 절대 서버 경로는 유출하지 않음.
        - 통과 시 `(물리경로, content_type, filename)` 반환.

- [x] **Step 3: Action Executor 아티팩트 저장 성공 시 메타데이터 자동 등록 연동 및 Best-Effort Cleanup**
  - 파일 경로: [orchestrator/actions.py](file:///d:/workspace/CLI-Execution-Platform/orchestrator/actions.py) [MODIFY]
  - 구현 내용:
    - `ActionExecutor.execute_attempt` 내에서 `self._storage.save_artifact` 호출이 성공적으로 완결되는 시점에 `ArtifactService.register_artifact`를 함께 호출하여 DB에 메타데이터 일관성 있게 등록.
    - DB 트랜잭션을 활용해 복사 및 메타데이터 등록 중 하나라도 실패하면 rollback 처리되고 성공 시에만 commit 되도록 연동.
    - **Best-Effort Cleanup**: 복사는 수행되었으나 DB 저장 실패 혹은 검증 예외 발생 시, 이미 artifacts/ 경로에 생성된 아티팩트 파일에 대하여 `os.remove` 또는 `Path.unlink` 등의 예외 핸들링을 적용하여 찌꺼기 파일 제거.

- [x] **Step 4: API 라우터에 다운로드 엔드포인트 구현**
  - 파일 경로: [jobs/router.py](file:///d:/workspace/CLI-Execution-Platform/jobs/router.py) [MODIFY]
  - 구현 내용:
    - `GET /api/v1/artifacts/{artifact_id}/download` API 엔드포인트 구현.
    - `db` 및 `storage_service`를 의존성 주입받아 `ArtifactService` 기동.
    - `ArtifactNotFoundError` 캐치 시 HTTP 404 응답 반환.
    - `ArtifactPermissionError` 캐치 시 HTTP 403 응답 반환.
    - 상세 에러 응답 본문 및 메세지에 절대 서버 경로가 누출되지 않도록 포맷 고정.
    - 성공 시 `FileResponse(path, media_type, filename)`을 통해 Content-Type 및 Content-Disposition 다운로드 파일명을 정확히 반환.

- [x] **Step 5: Artifact 보안 다운로드 관련 테스트 구현 (Symlink Escape 포함)**
  - 파일 경로: [tests/test_unit_2.py](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_2.py) [MODIFY]
  - 구현 내용:
    - 다음 시나리오의 자동화 테스트 케이스 추가 및 검증:
      - `test_artifact_registration_accepts_valid_paths`
      - `test_artifact_registration_rejects_absolute_paths`
      - `test_artifact_registration_rejects_traversal_segments`
      - `test_artifact_registration_rejects_windows_backslash`
      - `test_artifact_download_success` (Content-Type 및 파일명 검증)
      - `test_artifact_download_404_unknown_id`
      - `test_artifact_download_404_missing_physical_file`
      - `test_artifact_download_404_not_regular_file` (디렉토리 요청 시)
      - `test_artifact_download_403_traversal` (DB 메타데이터가 변조되어 `../`가 포함된 경우 재검증 차단)
      - `test_artifact_download_403_absolute`
      - `test_artifact_download_403_prefix_bypass` (접두사 우회 침입 차단)
      - `test_artifact_download_403_symlink_escape` (symlink를 활용해 샌드박스를 탈출하려는 경우 Path.resolve()를 통해 차단되는지 검증)
      - `test_artifact_download_no_server_path_disclosure` (실패 시 절대 서버 경로가 없는지 응답 본문 확인)

- [x] **Step 6: 전체 테스트 + 신규 테스트 전체 통과 확인 및 회귀 검증**
  - 실행 명령: 
    - `.\venv\Scripts\python -m pytest tests/ -v`
  - 확인 사항: 새로 추가된 보안 시나리오를 포함하여 총 79개+ 테스트가 회귀 에러 없이 안전하게 통과하는지 검증.

---

## 3. Story / Requirement Mappings

- **Requirement R-16 / Story S-8 (보안 Artifact 다운로드)**:
  - `jobs/models.py`, `jobs/service.py`, `orchestrator/actions.py`, `jobs/router.py` 코드 수정을 통해 ID 기반 다운로드 안전망 구축.
  - `tests/test_unit_2.py`에 물리 경로 우회, 403, 404, 성공 헤더 검증 테스트 스위트를 작성하여 추적성 보장.
