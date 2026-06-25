# 유닛 테스트 실행 지침 (Unit Test Execution Instructions)

본 지침은 CLI-Execution-Platform 프로젝트의 유닛 테스트 구성 및 실행 방법을 설명합니다. 특히 R-16(보안 아티팩트 다운로드 API) 및 R-17(Job ID 기반 아티팩트 목록 조회 API) 개발과 관련된 핵심 테스트 케이스의 검증 방식을 서술합니다.

## 테스트 실행 환경
- **테스트 러너**: `pytest`
- **테스트 경로**: `tests/`
- **사전 요구사항**: Python 가상환경이 활성화되고 `requirements.txt` 패키지들이 설치된 상태여야 합니다.

## 유닛 테스트 실행 방법

### 1. 전체 유닛 및 기능 테스트 실행
```bash
# Windows PowerShell
$env:PYTHONPATH="."
venv\Scripts\pytest

# Linux/macOS
export PYTHONPATH="."
pytest
```

### 2. 특정 테스트 모듈만 단독 실행 (R-16/R-17 아티팩트 검증 위주)
```bash
# Windows PowerShell
$env:PYTHONPATH="."
venv\Scripts\pytest tests/test_unit_2.py
```

## R-16 및 S-8 관련 핵심 유닛 테스트 케이스 목록

`tests/test_unit_2.py`에 추가된 R-16 아티팩트 보안 검증 테스트는 다음과 같습니다:

1. **정상 경로 등록 검증** (`test_artifact_registration_accepts_valid_paths`):
   - 정상적인 workspace 상대경로에 위치한 아티팩트의 정상 등록 확인.

2. **절대경로 등록 차단 검증** (`test_artifact_registration_rejects_absolute_paths`):
   - `/etc/passwd` 등 절대경로로 등록 시도 시 즉각 차단 및 예외 발생 확인.

3. **상대경로 탈출 등록 차단 검증** (`test_artifact_registration_rejects_traversal_segments`):
   - `../file.txt`, `dir/./file.txt`, `dir//file.txt` 등 비정상적인 세그먼트 등록 시도 시 차단 확인.

4. **Windows 역슬래시 등록 차단 검증** (`test_artifact_registration_rejects_windows_backslash`):
   - `models\\model.scad`와 같이 역슬래시가 포함된 경로 등록 차단 확인.

5. **성공적인 아티팩트 다운로드 검증** (`test_artifact_download_success`):
   - 아티팩트 ID를 기반으로 실제 workspace의 물리 파일이 정상 다운로드 경로를 반환하는지 확인.

6. **알 수 없는 아티팩트 ID 조회 시 404 반환** (`test_artifact_download_404_unknown_id`):
   - DB에 기록이 없는 UUID로 요청 시 404 예외 확인.

7. **물리 파일 누락 시 404 반환** (`test_artifact_download_404_missing_physical_file`):
   - DB 메타데이터는 있으나 실제 물리 파일이 삭제된 경우 404 예외 확인.

8. **일반 파일이 아닌 대상 조회 시 404 반환** (`test_artifact_download_404_not_regular_file`):
   - 디렉토리 등 일반 파일이 아닌 대상을 다운로드 하려 할 때 404 예외 확인.

9. **다운로드 시 경로 탈출 차단 403 반환** (`test_artifact_download_403_traversal`):
   - DB 위조 등으로 다운로드 시점에 `../`가 포함된 경로로 물리 파일 조회를 유도할 때 403 예외 확인.

10. **다운로드 시 절대경로 차단 403 반환** (`test_artifact_download_403_absolute`):
    - DB 내 절대경로 주입 공격 시 물리 분석 단계에서 403 예외 확인.

11. **다운로드 시 prefix-bypass 차단 403 반환** (`test_artifact_download_403_prefix_bypass`):
    - workspace 가 가령 `/tmp/jobs/job1` 일 때 `../job1_evil/file.txt` 등으로 prefix를 우회하려 할 때 403 예외 확인.

12. **다운로드 시 심볼릭 링크 이탈 차단 403 반환** (`test_artifact_download_403_symlink_escape`):
    - workspace 내부에 샌드박스 외부의 중요 파일(예: `outside_secret.txt`)을 가리키는 symlink를 생성한 뒤 다운로드 시도 시 물리 경로 검증에서 감지 및 403 예외 확인.

13. **절대 서버 경로 유출 차단 검증** (`test_artifact_download_no_server_path_disclosure`):
    - 에러 메시지에 `/etc/passwd` 등 서버의 물리 절대경로 정보가 유출되지 않고 논리 에러만 출력되는지 확인.

## R-17 관련 핵심 유닛 테스트 케이스 목록

`tests/test_unit_2.py`에 추가된 R-17 아티팩트 목록 조회 검증 테스트는 다음과 같습니다:

1. **성공적인 아티팩트 목록 조회 검증** (`test_get_artifacts_success`):
   - 완료(COMPLETED) 상태인 Job에 연계된 아티팩트가 있을 때 목록을 조회하면 200 OK와 함께 목록을 정상 반환하고, 보안상 물리적 정보가 포함된 `relative_path` 필드가 차단(제외)되었는지 검증합니다.

2. **존재하지 않는 Job ID 조회 시 404 반환** (`test_get_artifacts_not_found`):
   - 존재하지 않는 임의의 `job_id`로 목록을 조회할 시 HTTP 404 Not Found 및 `NOT_FOUND` 비즈니스 코드가 반환되는지 검증합니다.

3. **완료 상태가 아닌 Job 조회 시 400 반환** (`test_get_artifacts_not_completed`):
   - Job 상태가 `CREATED`, `RUNNING`, `FAILED` 인 경우 아티팩트 조회를 거부하고 HTTP 400 Bad Request 및 `BAD_REQUEST` 비즈니스 코드가 반환되는지 검증합니다.

## 결과 확인 및 트러블슈팅
- **기대 결과**: 모든 테스트 케이스가 통과해야 합니다. (기존 R-15/R-16 테스트를 포함한 전체 95개 테스트 통과 보장)
- 테스트 실패 시, `tests/test_unit_2.py` 및 관련 코드(`jobs/router.py`, `jobs/service.py`)의 구현 상태를 로그를 기반으로 분석하고 수정하십시오.
