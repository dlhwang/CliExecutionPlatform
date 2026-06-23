# 보안 테스트 지침 (Security Test Instructions)

본 지침은 CLI-Execution-Platform 프로젝트의 R-16 보안 사양을 만족하기 위한 보안 검증 절차 및 차단 방식을 설명합니다.

## 보안 요구사항 목적
클라이언트가 임의의 경로(예: `../etc/passwd`, 절대경로 등)를 지정하여 샌드박스 영역 바깥의 기밀 파일에 접근하지 못하도록 통제하고, 서버의 절대 경로가 에러를 통해 유출되지 않게 원천 차단하는 것입니다.

## 주요 보안 검증 항목 및 테스트 실행법

### 1. 경로 탈출 (Path Traversal) 시도 차단
- **개념**: `relative_path`에 `../` 세그먼트 등을 주입하여 상위 디렉토리로 이동하는 행위를 차단합니다.
- **수행 검증**:
  - `PurePosixPath` 기반 논리 분석을 수행하여 `..` 세그먼트가 포함되면 HTTP 403 Forbidden을 반환합니다.
- **테스트 케이스**: `test_artifact_registration_rejects_traversal_segments`, `test_artifact_download_403_traversal`

### 2. 절대경로 (Absolute Path) 차단
- **개념**: `/etc/passwd` 또는 `C:\Windows\System32\...`와 같이 절대경로를 입력해 시스템 영역에 접근하는 행위를 차단합니다.
- **수행 검증**:
  - `PurePosixPath.is_absolute()` 검사를 수행하여 절대경로 포맷일 경우 즉시 HTTP 403 Forbidden으로 차단합니다.
- **테스트 케이스**: `test_artifact_registration_rejects_absolute_paths`, `test_artifact_download_403_absolute`

### 3. 접두사 우회 (Prefix-Bypass) 차단
- **개념**: 샌드박스 디렉토리가 `/tmp/jobs/job1` 일 때, 상위 디렉토리 이동 후 글자수 매칭 방식을 우회하여 `/tmp/jobs/job1_evil/file` 등에 접근하는 공격을 차단합니다.
- **수행 검증**:
  - 단순 문자열 `startswith` 대신 `Path.resolve()`를 적용해 실제 물리적 주소를 구한 뒤, `is_relative_to(workspace_root)`를 통해 엄격하게 물리 영역 내부인지 확인합니다.
- **테스트 케이스**: `test_artifact_download_403_prefix_bypass`

### 4. 심볼릭 링크 이탈 (Symlink Escape) 차단
- **개념**: 샌드박스 영역 내부에 외부 중요 정보 파일을 가리키는 심볼릭 링크를 생성하여 다운로드를 유도하는 공격을 차단합니다.
- **수행 검증**:
  - `Path.resolve()`는 심볼릭 링크를 원본 파일의 실제 물리 경로로 완전히 해소(resolve)합니다. 해소된 물리 경로가 `workspace_root` 밖에 존재하면 차단합니다.
- **테스트 케이스**: `test_artifact_download_403_symlink_escape`

### 5. 서버 절대 경로 유출 차단 (No Server Path Disclosure)
- **개념**: 예외 발생 시 에러 메시지나 Stacktrace 내에 서버 로컬 절대 경로가 유출되면 안 됩니다.
- **수행 검증**:
  - 예외 발생 시 반환되는 에러 메시지에 시스템 폴더 구조나 경로 조각이 들어가지 않도록 마스킹 처리하여 사용자에게는 논리 검증 실패 원인만 제공합니다.
- **테스트 케이스**: `test_artifact_download_no_server_path_disclosure`

## 보안 테스트 자동화 도구
- 모든 보안 시나리오는 파이썬의 `pytest`를 활용해 자동으로 검증됩니다.
```bash
# 보안 관련 유닛 테스트 전체 구동
$env:PYTHONPATH="."
venv\Scripts\pytest tests/test_unit_2.py
```
- **합격 기준**: 모든 보안 우회 시나리오에 대해 적절하게 예외가 발생하여 예외가 통과(assert)되어야 합니다.
