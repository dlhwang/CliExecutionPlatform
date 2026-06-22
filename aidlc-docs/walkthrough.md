# Walkthrough - Hotfix R-14 (Docker 격리 실행 하위 경로 지원)

본 문서에서는 Docker 컨테이너 환경 격리 실행(/tmp 디렉토리) 과정에서 하위 디렉토리를 포함하는 결과물이 올바르게 생성되고 복사되도록 수정한 내역 및 검증 결과를 정리합니다.

## 1. 변경 사항 (Changes Made)

### CLI Runner Service
- `runner/service.py` 내 `_execute_with_timeout` 메서드를 수정하여 격리 실행 시 안정성과 보안을 모두 만족하는 다음의 로직을 적용했습니다:
  1. **디렉토리 구조 사전 재생성**: workspace 내부에 생성되어 있는 모든 하위 디렉토리 구조를 스캔하여 `/tmp/openscad_xxxx/` 하위에 동일하게 재생성합니다.
  2. **입력 소스 복사 (상대 경로 유지)**: workspace 내의 모든 `.scad` 소스 파일들을 상대 경로 구조 그대로 유지하면서 임시 디렉토리 아래의 해당 위치로 복사합니다.
  3. **출력 대상 부모 디렉토리 자동 생성**: CLI 실행 인자 중 `-o` 옵션을 감지 및 파싱하여, 명시된 출력 파일이 저장될 부모 디렉토리를 임시 디렉토리 하위에 미리 생성(`mkdir -p`)합니다.
  4. **경로 물리 검증**: 복사 및 생성되는 모든 경로에 대해 resolve 후 workspace(또는 tmp_path) 하위에 존재하는지 확인하여 Path Traversal 우회 공격을 완전 차단합니다.
  5. **파일 단위 스냅샷(Snapshot) 비교**: 프로세스 기동 전 임시 디렉토리 내의 파일 목록, 파일 크기, 수정 시간(mtime)을 파일 단위로 스냅샷을 생성하여 관리합니다.
  6. **선별적 결과 반영 및 충돌 방지**: 실행 완료 후, 스냅샷 대비 새로 생성되었거나 변경된 파일만 선별하여 workspace로 복사하며, `-o`로 명시된 출력 파일은 덮어쓰기를 허용하고 그 외의 원본 파일에 대한 덮어쓰기 시도는 엄격히 차단(예외 발생)합니다.

### 테스트 스위트
- `tests/test_deployment.py`의 `test_compose_defines_expected_services`를 수정하여 이전 db 서비스 통합 구성 요소의 검증이 깨지던 문제를 해결했습니다.
- `tests/test_unit_3.py`에 다음 테스트들을 추가 및 갱신했습니다:
  - `test_run_tool_uses_job_workspace_as_cwd`: 격리 실행 디렉토리(`/tmp`) 사용에 맞추어 검증 로직 갱신.
  - `test_run_tool_with_subdirectory_output_success` (신규): 실제 장애 상황과 동일한 `["-o", "dice_design/octahedron_dice.stl", "dice_design/octahedron_dice.scad"]` 인자 호출 시 정상적으로 성공하고 stl 파일이 복사되는지 검증.
  - `test_run_tool_with_traversal_output_fails` (신규): `../escape.stl` 이나 절대 경로를 출력 인자로 주었을 때 정상 차단되는지 방어 검증.

## 2. 테스트 및 검증 결과 (What was Tested)

- `pytest` 명령을 이용해 추가된 단위/통합 테스트와 기존의 모든 회귀 테스트를 로컬 환경(Windows PowerShell venv)에서 전원 구동했습니다.

### 검증 결과
- **실행 명령**: `.\venv\Scripts\python -m pytest`
- **테스트 결과**: 58개 테스트 전원 통과 (58 passed, 0 failed)
- **신규 테스트 동작**:
  - 하위 디렉토리를 포함하는 출력 및 상대 경로 스캐드 파일 복사가 `/tmp` 격리 구조 내에서 문제없이 성공함을 확인.
  - 상위 디렉토리로의 탈출을 시도하는 Path Traversal 악성 입력이 철저히 차단되고 예외가 던져짐을 확인.
