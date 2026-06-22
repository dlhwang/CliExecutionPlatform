# Code Generation Plan - Hotfix R-15B (CLI 런타임 출력 및 diagnostics)

본 계획서는 runner 계층의 실행 결과 계약을 강화하는 R-15B의 단일 진실 공급원입니다. 오케스트레이터 retry 흐름과 plan 저장 시점은 R-15C 범위이며 본 단계에서는 변경하지 않습니다.

## 1. 범위와 의존성

- **선행 조건**: R-15A 완료
- **대상**: `runner/exceptions.py`, `runner/service.py`, `runner/diagnostics.py`, `tests/test_unit_3.py`
- **비대상**: `llm/retry.py`, `orchestrator/service.py`, action plan 저장 시점
- **계약**: `CLIExecutionError`가 exit code와 bounded stdout/stderr를 제공하고, diagnostics가 LLM에 전달 가능한 bounded 메시지를 생성한다.
- **Refinement 경계**: R-15B는 runtime refinement에 사용할 진단 payload를 생성한다. parse→validation→execution 재시도 제어와 LLM 전달은 R-15C의 단일 소유 범위다.

## 2. Code Generation Checklists

- [x] **Step B1: `CLIExecutionError` 출력 계약 확장**
  - `stdout`, `stderr`, `exit_code` 속성을 추가한다.
  - `CLIExecutionError.__str__`는 bounded stdout/stderr tail만 포함한다.
  - 전체 process output, 생성된 SCAD content, action plan JSON, traceback은 예외 문자열에 포함하지 않는다.
  - 기존 생성자 호출과 하위 예외의 호환성을 유지한다.

- [x] **Step B2: stdout/stderr 분리 수집 및 EventLog 호환성 유지**
  - OpenSCAD stdout과 stderr를 concurrent task로 drain하여 subprocess pipe deadlock을 방지한다.
  - 각 스트림의 최근 출력만 독립된 bounded tail로 메모리에 보존한다.
  - stdout/stderr의 각 완성 line과 마지막 remainder를 기존 `CLI_OUTPUT` 이벤트로 계속 저장한다.
  - timeout 시 두 스트림의 부분 로그 보존을 유지한다.

- [x] **Step B3: OpenSCAD runtime diagnostics 추가**
  - `Current top level object is empty.`를 `[SCAD_EMPTY_TOP_LEVEL]`로 분류한다.
  - `Ignoring 3D child object for 2D operation`을 `[SCAD_2D_3D_MIXED_OPERATION]`으로 분류한다.
  - 알려진 진단이 없으면 exit code와 bounded stderr/stdout tail을 제공한다.
  - diagnostics 입력은 `CLIExecutionError`의 bounded stdout/stderr tail로만 제한한다.
  - Rule ID, 짧은 설명, bounded 대표 출력만 포함한 feedback을 반환한다.
  - 전체 process output, SCAD content, action plan JSON, traceback을 받거나 포함하는 API를 만들지 않는다.

- [x] **Step B4: runner 및 diagnostics 테스트**
  - stdout/stderr와 exit code가 예외에 포함되는지 검증한다.
  - tail의 라인 수와 전체 길이가 제한되는지 검증한다.
  - `CLIExecutionError.__str__`와 diagnostics에 tail 밖의 sentinel, 전체 SCAD, plan JSON, traceback이 포함되지 않는지 검증한다.
  - 두 pipe가 동시에 대량 출력해도 deadlock 없이 종료되고 모든 emitted line이 `CLI_OUTPUT`으로 저장되는지 검증한다.
  - 두 OpenSCAD 메시지가 안정적인 Rule ID로 분류되는지 검증한다.
  - timeout, non-zero exit, EventLog 저장의 기존 테스트를 회귀 검증한다.

- [x] **Step B5: R-15B 테스트 실행 및 결과 기록**
  - `.\venv\Scripts\python -m pytest tests/test_unit_3.py -v`
  - `.\venv\Scripts\python -m pytest tests/ -v`

## 3. 완료 조건

- runner만으로 실패 원인과 bounded diagnostics를 제공할 수 있다.
- 오케스트레이터 동작과 plan 저장 시점은 변경되지 않는다.
- `ScadStaticValidator`의 2D/3D 정적 휴리스틱은 런타임 문자열 감지로 요구사항이 충족되고 오탐 위험이 있으므로 N/A로 기록한다.
