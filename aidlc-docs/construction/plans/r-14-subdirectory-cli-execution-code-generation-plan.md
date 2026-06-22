# Code Generation Plan - Hotfix R-14 (Docker 격리 실행 시 하위 디렉토리 생성 및 복사)

본 문서는 Docker 격리 실행(/tmp 디렉토리) 중 하위 디렉토리(예: `dice_design/octahedron_dice.stl`)를 포함하는 출력 경로를 올바르게 처리하기 위한 코드 변경 및 테스트 계획을 담고 있습니다.

## 1. Unit Context & Traceability
- **Target Unit**: CLI Runner Service (`runner/service.py`)
- **Implemented Requirement**: Requirement R-14 (Docker 컨테이너 환경에서 하위 디렉토리를 포함한 CLI 실행 결과 파일 복사 및 격리 실행 호환성)
- **Primary Risks**: 
  - 복사 과정 중 기존 workspace 파일 덮어쓰기 오작동 위험
  - 디렉토리 구조 스캔 및 복사 과정에서의 Path Traversal 방지 보안 무결성 유지

## 2. Requirement Verification Plan

| Requirement | Acceptance Criteria | Required Test Evidence | Test Level | Planned Test File/Scenario | Required Result |
| --- | --- | --- | --- | --- | --- |
| R-14 | 실제 장애 케이스 호환 | `run_tool` 호출 시 `["-o", "dice_design/octahedron_dice.stl", "dice_design/octahedron_dice.scad"]` 형태의 하위 입출력 경로 성공 검증 | unit/integration | `tests/test_unit_3.py` 내 `test_run_tool_with_subdirectory_output_success` | Pass |
| R-14 | Path Traversal 방어 | `../escape.stl` 등 상위 탈출 경로나 절대 경로 출력이 차단되는지 검증 | unit/integration | `tests/test_unit_3.py` 내 `test_run_tool_with_traversal_output_fails` | Pass (예외 발생) |
| 회귀 방지 | 기존 동작 유지 | 전체 테스트 실행 | regression | `pytest -q` | 모든 테스트 통과 (56개 이상) |

## 3. Detailed Code Generation Steps

- [x] **Step 1: Check Workspace & Prepare Environment**
  - 대상 파일인 `runner/service.py`와 `tests/test_unit_3.py` 상태를 확인하고, git status가 깨끗한지(또는 이전 커밋 보존) 확인합니다.
- [x] **Step 2: Modify `runner/service.py` - Setup directory structures & input files in `/tmp`**
  - `_execute_with_timeout` 메서드 내에서 임시 디렉토리 `/tmp/openscad_xxxx/`를 생성한 후:
    1. **디렉토리 구조 사전 생성**: workspace 내에 존재하는 모든 하위 디렉토리 구조를 스캔하여 임시 디렉토리 하위에 동일하게 미리 생성합니다.
    2. **입력 파일 복사 및 상대경로 유지**: workspace 하위의 모든 `.scad` 소스 파일들을 상대 경로 구조 그대로 유지하며 임시 디렉토리 하위의 해당 위치로 복사합니다.
    3. **출력 부모 디렉토리 자동 생성 (-o 한정)**: `args` 중 실제 사용 중인 `-o` 출력 옵션을 파싱하여, 그 뒤에 지정된 출력 경로의 부모 디렉토리가 임시 디렉토리 내에 없으면 사전에 생성합니다 (`Path.mkdir(parents=True, exist_ok=True)`). `--output` 등의 기타 옵션은 파싱하지 않고 `-o`에 한정합니다.
    4. **경로 검증**: 모든 파일 복사 및 디렉토리 생성 경로는 resolve 후 workspace 내부인지 확인하여 Path Traversal 우회를 원천 차단합니다.
- [x] **Step 3: Modify `runner/service.py` - Copy newly generated/modified files back using file snapshots**
  - CLI 실행 시작 전, 임시 디렉토리 내의 모든 **파일(디렉토리 제외)**을 대상으로 파일 경로, 파일 크기, 수정 시간(mtime)을 **파일 기준 Snapshot**으로 기록합니다.
  - CLI 실행 완료 후, 임시 디렉토리를 재귀적으로 조회하여 실행 전 Snapshot과 파일 기준으로 비교합니다.
  - **선별적 복사 및 충돌 차단**:
    - Snapshot에 존재하지 않던 새로 생성된 파일/디렉토리 구조 및 Snapshot 대비 수정 시간(mtime)이나 파일 크기가 변경된 파일들만 선별하여 workspace에 복사합니다.
    - 이때 `-o`로 명시된 출력 파일은 덮어쓰기를 허용하지만, 그 외 기존 workspace에 이미 존재하고 변경되지 않은 원본 파일들이 불필요하게 덮어쓰여지는 충돌 현상을 방지(무시 혹은 예외 처리)합니다.
  - **보안/NFR 유지**: 기존 timeout(30초), resource limit, Path Traversal 방어 로직은 손상 없이 유지합니다.
- [x] **Step 4: Update `tests/test_unit_3.py` - Add subdirectory verification & defense tests**
  - `tests/test_unit_3.py` 파일 내에 다음 테스트들을 추가합니다:
    1. **장애 재현 및 성공 테스트**: `test_run_tool_with_subdirectory_output_success`
       - OpenSCAD 인자로 `["-o", "dice_design/octahedron_dice.stl", "dice_design/octahedron_dice.scad"]` 형태의 하위 디렉토리 입출력을 지정하여 호출했을 때, 임시 폴더에서 정상 실행되고 최종 workspace 내 `dice_design/octahedron_dice.stl` 파일이 정상 복사되어 존재하는지 검증합니다.
    2. **Path Traversal 방어 테스트**: `test_run_tool_with_traversal_output_fails`
       - `-o` 뒤의 인자로 `../escape.stl` 등 상위 디렉토리 탈출 시도나 절대경로가 주어졌을 때 올바르게 차단되고 `CLIArgumentValidationError`가 발생함을 검증합니다.
- [x] **Step 5: Run verification and regression tests**
  - `pytest` 명령을 이용해 추가된 신규 테스트와 기존의 모든 회귀 테스트가 성공적으로 작동하는지 검증합니다. (56개 이상의 테스트 전원 통과 확인)
- [x] **Step 6: Document results**
  - 작업 결과를 정리하고 `walkthrough.md`를 갱신합니다.
