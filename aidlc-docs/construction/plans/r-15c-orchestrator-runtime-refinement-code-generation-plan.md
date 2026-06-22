# Code Generation Plan - Hotfix R-15C (오케스트레이터 runtime refinement)

본 계획서는 R-15B의 bounded CLI diagnostics를 LLM refinement에 연결하고 오케스트레이터 실행·저장 순서를 변경하는 R-15C의 단일 진실 공급원입니다.

## 1. 범위와 의존성

- **선행 조건**: R-15B 구현 및 테스트 승인
- **대상**: `llm/retry.py`, `orchestrator/service.py`, `orchestrator/actions.py`, storage attempt rollback/promotion 경계, `tests/test_unit_5.py`
- **핵심 위험**: 실행 콜백 재시도 시 이미 수행된 파일 쓰기·디렉터리 생성 등 부작용이 workspace에 남을 수 있다.
- **격리 정책**: 실행 전 workspace snapshot, 실패 시 정확한 rollback, 성공 전 `CREATE_ARTIFACT` 승격 지연을 isolated attempt workspace와 동등한 정책으로 채택하고 테스트로 고정한다.
- **비대상**: non-idempotent external side effect는 runtime refinement retry 경계 밖에 둔다.

## 2. Code Generation Checklists

- [x] **Step C1: 실행 콜백 및 runtime refinement 계약 구현**
  - `LLMPlanRetryExecutor.generate_actions`에 비동기 `execution_cb`를 추가한다.
  - `generate_actions`를 parse → validation → execution refinement의 단일 소유자로 만든다.
  - `execution_cb`는 validation 성공 후, 최종 actions 반환 전에 호출한다.
  - `CLIExecutionError`의 R-15B bounded diagnostics만 현재 시도의 retry feedback으로 전달한다.
  - feedback에는 현재 attempt 실패만 포함하고 과거 feedback을 누적하지 않는다.
  - validation과 execution까지 성공한 attempt의 actions만 반환한다.
  - 재시도 소진 시 마지막 bounded failure를 상위 계층으로 전달한다.

- [x] **Step C2: 재시도 부작용 경계 구현**
  - 각 실행 attempt 전에 workspace file snapshot을 생성한다.
  - 실패 시 신규 파일을 제거하고 변경·삭제된 기존 파일을 복구하는 rollback을 적용한다.
  - `CREATE_ARTIFACT`는 나머지 retry-boundary action이 모두 성공할 때까지 지연하여 failed attempt artifact가 최종 artifact로 승격되지 않게 한다.
  - retry boundary는 workspace-local idempotent action과 OpenSCAD 실행으로 제한하고 non-idempotent external side effect를 제외한다.

- [x] **Step C3: 오케스트레이터 실행 흐름 단일화**
  - 별도 action 실행을 retry executor의 `execution_cb`로 이동한다.
  - 생성·parse·validation·execution이 모두 성공하여 반환된 최종 plan만 저장한다.
  - `PLAN_VALIDATED` 이벤트 명칭 또는 발생 시점이 실제 의미와 일치하도록 조정한다.
  - 최종 plan persistence와 실행 성공 이후에만 Job을 `COMPLETED`로 전이한다.
  - 재시도 소진 시 bounded failure reason으로 Job을 `FAILED`로 전이한다.

- [x] **Step C4: 통합 및 상태 전이 테스트**
  - 첫 CLI 실행 실패 후 두 번째 LLM plan 실행이 성공하는지 검증한다.
  - retry feedback에 Rule ID가 포함되고 전체 출력이나 과거 feedback이 누적되지 않는지 검증한다.
  - 실패한 첫 plan이 최종 action plan으로 저장되지 않는지 검증한다.
  - execution 성공 전 actions가 반환되거나 저장되지 않는지 검증한다.
  - 실패 attempt의 workspace 변경과 artifact가 rollback되고 최종 승격되지 않는지 검증한다.
  - non-idempotent external side effect가 retry callback에 들어가지 않는지 검증한다.
  - 최종 plan persistence → `COMPLETED` 순서와 retry 소진 → bounded reason `FAILED` 전이를 검증한다.

- [x] **Step C5: R-15C 전체 회귀 테스트 및 결과 기록**
  - `.\venv\Scripts\python -m pytest tests/test_unit_5.py -v`
  - `.\venv\Scripts\python -m pytest tests/ -v`

## 3. 완료 조건

- 런타임 실패가 bounded LLM feedback으로 한 번씩 전달된다.
- 성공한 최종 plan만 저장되며 상태·이벤트 순서가 테스트로 증명된다.
- 재시도 부작용 정책이 명시되고 자동화 테스트로 검증된다.

## 4. Additional Contract Traceability

1. `generate_actions` single owner: Step C1
2. `execution_cb` ordering: Step C1
3. R-15B bounded diagnostics conversion: Step C1
4. Current-attempt-only feedback: Step C1, C4
5. Successfully executed actions only: Step C1, C3, C4
6. Equivalent isolated attempt policy: Step C2, C4
7. Failed artifact non-promotion: Step C2, C4
8. Non-idempotent side effects excluded: Step C2, C4
9. Persistence and `COMPLETED` ordering: Step C3, C4
10. Exhaustion and bounded `FAILED` reason: Step C1, C3, C4
