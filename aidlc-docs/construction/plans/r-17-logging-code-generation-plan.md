# Code Generation Plan - HOTFIX R-17-LOGGING (아티팩트 생명주기 로깅 및 경로 검증 개선)

본 계획서는 아티팩트 라이프사이클 11가지 상세 이벤트 로그 마커 주입 및 경로 검증부 오류 상세 로그 출력을 안전하게 구현하기 위한 코드 작성 절차를 정의합니다.

## Unit Context & Traceability

- **Feature / Hotfix**: HOTFIX R-17-LOGGING (아티팩트 생명주기 로깅 및 경로 검증 개선)
- **Target Requirements**: Requirement R-17-LOGGING (아티팩트 생명주기 로깅 및 경로 검증 디버그 정보 보강)
- **Dependencies**: 기존 `StorageService`, `ArtifactService`, `CLIExecutionRunner` 모듈에 내포된 로깅 부족 및 예외 삼킴 현상 개선.
- **Security Scope**: 절대 호스트 서버 경로가 사용자 응답 본문(HTTP Response Body)에 노출되지 않도록 기존 에러 메시지 은폐 보안 원칙 준수.

---

## Code Generation Steps

### [Business Logic & Logging Enhancement]

- [x] **Step 1: `storage/local.py` 로깅 모듈 임포트 및 마커 적용**
  - 파일 상단에 `import logging` 및 `logger = logging.getLogger(__name__)` 선언 추가.
  - `_validate_safe_path` 내에 경로 resolve 값 및 `is_relative_to` 실패 시 세부 원인(ValueError 및 경로 쌍)을 포함하는 경고 로그 작성.
  - `check_artifact_exists` 내에서 `PermissionError`를 잡기 전 `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 마커 및 타겟 경로 쌍 상세 로깅 작성.
  - `save_artifact` 내에 복사 시도(`[ARTIFACT_COPY_STARTED]`), 복사 성공(`[ARTIFACT_COPY_COMPLETED]`), 복사 실패(`[ARTIFACT_COPY_FAILED]`) 로깅 및 경로 출력 작성.
  
- [x] **Step 2: `jobs/service.py` 로깅 모듈 임포트 및 ArtifactService 마커 적용**
  - 파일 상단에 `import logging` 및 `logger = logging.getLogger(__name__)` 선언 추가.
  - `ArtifactService.register_artifact` 내에 등록 시작(`[ARTIFACT_METADATA_CREATE_STARTED]`), 등록 완료(`[ARTIFACT_METADATA_CREATE_COMPLETED]`) 로깅 작성.
  - `ArtifactService.get_artifact_for_download` 내에 DB 조회 실패(`[ARTIFACT_DOWNLOAD_METADATA_NOT_FOUND]`), 경로 검증 실패(`[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 및 세부 경로 출력), 물리 파일 부재(`[ARTIFACT_DOWNLOAD_FILE_NOT_FOUND]`), 모든 검사 통과 및 성공(`[ARTIFACT_DOWNLOAD_READY]`) 마커 로깅 작성.

- [x] **Step 3: `jobs/router.py` API 다운로드 진입부 로깅 마커 적용**
  - `download_artifact` 및 `download_artifact_by_id` 도입부에 `[ARTIFACT_DOWNLOAD_REQUESTED]` 로깅 작성.

- [x] **Step 4: `runner/service.py` 생성 완료 시점 마커 적용**
  - `_execute_with_timeout` 메서드 내부에서, CLI 실행 결과 파일 복사가 workspace target으로 정상적으로 성공하여 끝난 시점에 `[ARTIFACT_GENERATION_COMPLETED]` 마커 로깅 작성.

### [Verification & Testing]

- [x] **Step 5: `tests/test_unit_2.py` / `tests/test_unit_3.py` 디버그 로깅 및 마커 정상 출력 단위 테스트 구현**
  - `pytest` `caplog` 기능을 이용하여 아티팩트 다운로드 및 경로 검증 실패 시, 지정된 11개 로그 마커가 정상적으로 포맷팅되어 콘솔에 남는지 검증하는 신규 테스트 케이스 추가.
  - 예외 발생(디렉토리 traversal, prefix-bypass 등) 모의 시나리오 실행 시 `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 및 경로 검증 상세 정보가 서버 로그에 올바르게 기록되는지 확인.
  - 다운로드 실패 시 HTTP 에러 응답 본문에 실제 서버 내 호스트 절대 경로 정보가 노출되지 않음을 단언(Assert) 검증.

- [x] **Step 6: 전체 회귀 테스트 검증 및 빌드 확인**
  - `pytest` 도구를 통해 기존 95개 테스트 케이스를 포함한 전체 테스트 스위트의 100% 통과 확인.

