# Walkthrough - Hotfix R-17-LOGGING (아티팩트 생명주기 로깅 및 경로 검증 개선)

본 문서에서는 Mac Docker UI 및 로컬 개발 환경에서의 아티팩트 다운로드 실패 원인을 진단하고, 아티팩트 생명주기를 완벽히 추적할 수 있도록 11가지의 상세 이벤트 로그 마커를 보강한 내역 및 검증 결과를 정리합니다.

## 1. 변경 사항 (Changes Made)

### 로깅 마커 주입 및 경로 디버깅 정보 보강
* **`storage/local.py`**
  - 파일 상단에 `import logging` 및 `logger` 정의 추가.
  - `_validate_safe_path` 에서 문자열 traversal 감지 실패 시 `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 로깅 처리.
  - `_validate_safe_path` 에서 `is_relative_to` 검증 시 상세 resolve 경로 쌍(`target_path`, `base_job_dir`) 및 ValueError 원인을 포함하여 경고 로깅 처리.
  - `check_artifact_exists` 내에서 `PermissionError`를 삼키기 직전에 `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 마커 및 타겟 경로 쌍 상세 로깅 처리.
  - `save_artifact` 내에 복사 시작(`[ARTIFACT_COPY_STARTED]`), 복사 성공(`[ARTIFACT_COPY_COMPLETED]`), 복사 실패(`[ARTIFACT_COPY_FAILED]`) 로깅 추가.
* **`jobs/service.py`**
  - 파일 상단에 `import logging` 및 `logger` 정의 추가.
  - `register_artifact` 시작 및 완료 시점에 `[ARTIFACT_METADATA_CREATE_STARTED]`, `[ARTIFACT_METADATA_CREATE_COMPLETED]` 로깅 주입.
  - `get_artifact_for_download` 내에서 DB 조회 실패, 논리 검사 거부, 물리 검사(`is_relative_to`) 거부, 파일 누락 분기 시점에 각각 `[ARTIFACT_DOWNLOAD_METADATA_NOT_FOUND]`, `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]`, `[ARTIFACT_DOWNLOAD_FILE_NOT_FOUND]` 마커 및 실제 파일 경로 로깅 주입.
  - 모든 검사 통과 및 다운로드 준비 완료 시점에 `[ARTIFACT_DOWNLOAD_READY]` 마커 로깅 주입.
* **`jobs/router.py`**
  - `download_artifact` 및 `download_artifact_by_id` 도입부에 `[ARTIFACT_DOWNLOAD_REQUESTED]` 로깅 주입.
  - `download_artifact` 파일 스트리밍 반환 직전에 `[ARTIFACT_DOWNLOAD_READY]` 로깅 주입.
  - `download_artifact` 물리 파일 누락 예외 발생 시 `[ARTIFACT_DOWNLOAD_FILE_NOT_FOUND]` 로깅 주입.
* **`runner/service.py`**
  - 파일 상단에 `import logging` 및 `logger` 정의 추가.
  - CLI 도구 실행 종료 후 생성 결과물을 workspace로 성공 이관 완료한 시점에 `[ARTIFACT_GENERATION_COMPLETED]` 마커 로깅 주입.

### 테스트 스위트 보강
* **`tests/test_unit_2.py`**
  - `test_artifact_lifecycle_logging_markers` 테스트 케이스 추가.
  - `pytest` `caplog`를 사용해 아티팩트 라이프사이클 전 영역의 마커 출력을 모니터링하여 정상 출력됨을 단언 검증.
  - 심볼릭 링크 탈출 시나리오(물리 경로 검증 실패) 모의 시, `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 마커와 함께 resolve 경로 정보들이 로깅되는지 검증.
  - 다운로드 에러 시 HTTP Response Body에는 호스트 절대 서버 경로가 일체 노출되지 않음을 단언 검증.

---

## 2. 테스트 및 검증 결과 (What was Tested)

- `pytest` 명령을 이용해 추가된 단위/통합 테스트와 기존의 모든 회귀 테스트를 로컬 환경(Windows PowerShell venv)에서 전원 구동했습니다.

### 검증 결과
- **실행 명령**: `$env:PYTHONPATH="."; .\venv\Scripts\pytest`
- **테스트 결과**: 96개 테스트 전원 통과 (96 passed, 0 failed)
- **주요 로그 마커 및 디버깅 확인 동작**:
  - 정상적인 아티팩트 메타데이터 등록, 파일 복사, 다운로드 준비 단계를 거칠 때 콘솔에 `[ARTIFACT_METADATA_CREATE_STARTED]`, `[ARTIFACT_COPY_COMPLETED]`, `[ARTIFACT_DOWNLOAD_READY]` 등이 올바르게 찍히는 것 확인.
  - 비정상적인 경로 검사(심볼릭 링크 탈출 등) 시 `[ARTIFACT_DOWNLOAD_PATH_VALIDATION_FAILED]` 로그가 resolve된 경로 쌍과 함께 정확히 WARNING/ERROR 수준으로 콘솔에 기록되는 것 확인.
  - HTTP 예외 및 에러 응답 본문 내에 호스트의 내부 절대 경로 정보는 마스킹되어 유출되지 않음을 최종 확인.
