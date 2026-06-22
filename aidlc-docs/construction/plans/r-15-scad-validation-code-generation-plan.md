# Code Generation Plan - Hotfix R-15A (정적 검증 및 bounded validation feedback)

본 계획서는 R-15A의 완료된 정적 검증 범위를 기록하는 단일 진실 공급원(Single Source of Truth)입니다. CLI 런타임 출력·진단은 R-15B, 오케스트레이터 실행 흐름 변경은 R-15C에서 별도로 다룹니다.

## 1. Unit Context & Details

- **대상 영역**: LLM Client, Retry Executor, Security Validator, Unit Test
- **목적**: 
  - LLM에게 마크다운 펜스, prose, vector 속성 접근 금지 및 trigonometric degree 준수를 강제하는 prompt 최적화. (단, JSON Action Plan 스키마는 훼손되지 않도록 `.scad` 파일 내용 내부에만 적용)
  - LLM이 plan을 리턴하여 parsing 및 validation하는 단계에서 scad 구문에 대한 정적 검증(Lightweight Static Validation) 수행.
  - 검증 위반 시 `LLMPlanValidationError`를 던져 refinement loop에 에러 피드백을 전달하여 llm이 다시 작성하도록 유도.
- **예외 전이 및 단일화**: 
  - `LLMPlanRetryExecutor`에 `validation_cb` 콜백을 주입하여 `SecurityPolicyValidator.validate_actions` 내부로 검증 호출 위치 단일화.
  - 콜백 검증 과정에서 scad 구문 위반 시 `LLMPlanValidationError` 발생.
  - `LLMPlanRetryExecutor`가 이를 catch하여 `feedback = exc.message` 형태로 refinement 피드백 루프에 전달.

---

## 2. Code Generation Checklists

- [x] **Step 1: Scad 정적 검증 모듈 추가**
  - 파일 경로: [llm/scad_validator.py](file:///d:/workspace/CLI-Execution-Platform/llm/scad_validator.py) [NEW]
  - 구현 내용: 
    - `strip_comments(content)`: double-quoted string을 온전히 인식하여 문자열 내부의 `//` 또는 `/* */`가 오인 제거되지 않도록 문자 단위 순회를 도는 상태 머신(State Machine) 구현.
    - `ScadStaticValidator.validate(content)`: 7대 정적 검사 규칙을 구현하고 에러 시 Rule ID 태그(`[SCAD_SINGLE_QUOTE]`, `[SCAD_VECTOR_PROPERTY_ACCESS]` 등)를 붙인 오류 메시지를 모아 `LLMPlanValidationError` 발생.

- [x] **Step 2: LLM System Prompt 보강**
  - 파일 경로: [llm/client.py](file:///d:/workspace/CLI-Execution-Platform/llm/client.py) [MODIFY]
  - 구현 내용: 
    - `system_prompt` 내 OpenSCAD 액션 생성 가이드 및 RULES 섹션 보강.
    - 마크다운 펜스 및 prose 설명글 금지 사항은 오직 `.scad` 파일 content 내부에만 적용되며, 전체 JSON Action Plan 스키마는 준수해야 함을 지시.

- [x] **Step 3: Retry Executor Refinement Loop 연동 및 콜백 주입**
  - 파일 경로: [llm/retry.py](file:///d:/workspace/CLI-Execution-Platform/llm/retry.py) [MODIFY]
  - 구현 내용:
    - `generate_actions`의 인자로 `validation_cb: Callable[[Any], None] | None = None`을 받을 수 있도록 확장.
    - 파싱 성공 직후 `validation_cb`를 수행하여 validation 계층과 동적으로 유연하게 결합.
    - `except LLMPlanValidationError as exc`를 추가하여, scad 구문 위반을 포함한 validation 실패 시에도 `feedback = exc.message`를 전달해 LLM이 refinement 루프를 타며 코드를 재작성하도록 조치.

- [x] **Step 4: Security Policy Validator에 Scad 검증 추가 및 Service 계층 연동**
  - 파일 경로: [llm/validator.py](file:///d:/workspace/CLI-Execution-Platform/llm/validator.py) [MODIFY], [orchestrator/service.py](file:///d:/workspace/CLI-Execution-Platform/orchestrator/service.py) [MODIFY]
  - 구현 내용:
    - `SecurityPolicyValidator.validate_actions` 내부에서 `WRITE_FILE` 액션 중 `.scad` 파일 확장자인 경우 `ScadStaticValidator.validate(action_obj.content)`를 실행하는 단일 검증 로직 통합.
    - `JobOrchestratorService._run_in_slot`에서 `validation_cb`를 정의하고 `generate_actions(..., validation_cb=validation_cb)` 형태로 넘김. 기존 외부의 중복 `validate_actions` 호출 제거.

- [x] **Step 5: Scad 정적 검증 유닛 테스트 구현**
  - 파일 경로: [tests/test_unit_2.py](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_2.py) [MODIFY]
  - 구현 내용:
    - `ScadStaticValidator`의 10대 유닛 테스트 구현:
      - `test_scad_static_validation_rejects_vector_property_access`
      - `test_scad_static_validation_rejects_single_quotes`
      - `test_scad_static_validation_rejects_180_div_pi`
      - `test_scad_static_validation_rejects_pi_div_180`
      - `test_scad_static_validation_rejects_markdown_fence`
      - `test_scad_static_validation_rejects_prose`
      - `test_scad_static_validation_rejects_empty_file`
      - `test_scad_static_validation_rejects_missing_scad_keyword`
      - `test_scad_static_validation_accepts_valid_scad`
      - `test_scad_static_validation_ignores_comment_only_forbidden_patterns`

- [x] **Step 6: Orchestrator Refinement 통합 테스트 구현**
  - 파일 경로: [tests/test_unit_5.py](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_5.py) [MODIFY]
  - 구현 내용:
    - refinement 루프가 scad static validation 실패 시 에러 피드백을 전달하고 재시도가 완료되는지 검증하는 `test_orchestrator_refines_when_scad_static_validation_fails` 통합 테스트 작성.


- [x] **Step 7: 기존 전체 테스트 + 신규 테스트 전체 통과 확인**
  - 실행 명령: 
    - `.\venv\Scripts\python -m pytest tests/ -v`
  - 확인 사항: 기존 전체 테스트 및 신규 테스트 모두 안전하게 통과하는지 회귀 검증.

- [x] **Step 8: Refinement 피드백 토큰 폭발 방지 기능 구현**
  - 파일 경로: [llm/scad_validator.py](file:///d:/workspace/CLI-Execution-Platform/llm/scad_validator.py) [MODIFY]
  - 구현 내용:
    - `strip_comments`: multiline block comment 내부의 newline 보존하도록 하여 라인 넘버 맵핑이 원본과 정확히 1:1 유지되도록 개선.
    - `ScadStaticValidator.validate`: 7대 규칙에 대해 위반 라인 리스트를 구하고, 위반당 최대 1~2개 snippet(최대 150자 제한, 초과 시 `...` truncate) 추출.
    - 전체 에러 피드백 문자열의 길이를 조립할 때 최대 1,500자를 넘지 않도록 제한 및 추가 위반 생략 문구(`... [additional violations omitted]`) 추가.

- [x] **Step 9: 신규 토큰 폭발 방지 테스트 케이스 추가 및 검증**
  - 파일 경로: [tests/test_unit_2.py](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_2.py) [MODIFY]
  - 구현 내용:
    - `test_scad_validation_feedback_does_not_include_full_content` 구현: 100줄이 넘는 SCAD 내용 입력 시, 원본 전체가 아닌 위반 라인 snippet만 피드백에 도출되는지 검증.
    - `test_scad_validation_feedback_is_bounded` 구현: 다수의 에러를 내포한 대량의 SCAD 입력 시, 총 피드백 길이가 1,500자 이하로 제한되고 Rule ID와 생략 메시지가 유지되는지 검증.

- [x] **Step 10: 전체 테스트 수행 및 회귀 검증**
  - 실행 명령: 
    - `.\venv\Scripts\python -m pytest tests/ -v`
  - 확인 사항: 모든 신규/기존 테스트가 성공적으로 동작하는지 검증.

- [x] **Step A11: 원본 위치 보존 comment/string masking 보완**
  - 파일 경로: [llm/scad_validator.py](file:///d:/workspace/CLI-Execution-Platform/llm/scad_validator.py) [MODIFY]
  - 구현 내용:
    - 주석을 삭제하지 않고 newline과 문자 위치를 보존하는 공백 masking으로 변경한다.
    - syntax-like 규칙 전용 분석 view에서는 double-quoted string literal도 공백으로 masking하되 newline과 원본 line number를 유지한다.
    - escaped quote와 문자열 내부의 `//`, `/* */`를 올바르게 처리한다.
    - Markdown fence 등 raw-content 규칙, syntax-like 규칙, 구조 키워드 규칙이 각각 적절한 분석 view를 사용하도록 rule matrix를 명시한다.

- [x] **Step A12: false-positive 및 bounded feedback 테스트 보완**
  - 파일 경로: [tests/test_unit_2.py](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_2.py) [MODIFY]
  - 구현 내용:
    - 주석 및 double-quoted string 내부의 `point.x`, `180/PI`, `PI/180`이 위반으로 검출되지 않는지 검증한다.
    - 동일 패턴이 실행 코드에 있으면 원본 line number로 검출되는지 검증한다.
    - feedback이 bounded rule summary와 대표 원본 line snippet만 포함하고 전체 SCAD content는 포함하지 않는지 검증한다.

- [x] **Step A13: R-15A 보완 회귀 테스트 및 결과 기록**
  - `.\venv\Scripts\python -m pytest tests/test_unit_2.py -v`
  - `.\venv\Scripts\python -m pytest tests/ -v`

---

## 3. Story / Requirement Mappings

- **Requirement R-15A**:
  - `llm/scad_validator.py`, `llm/client.py`, `llm/retry.py`, `llm/validator.py`, `orchestrator/service.py` 코드 보완을 통해 단일화된 검증기 구축 및 refinement loop 연동.
  - `tests/test_unit_2.py`, `tests/test_unit_5.py`에 유닛 및 통합 검증용 테스트 추가하여 Requirements 추적성 충족.
  - [보완] 토큰 폭발 방지를 위해 검증 피드백 길이 제한(1,500자) 및 위반 라인 snippet화(최대 2개, 150자 제한), 이전 피드백 누적 방지 기법 적용.
  - [보완] `shutil.copy2(...)` 사용을 제거하고 산출물 복사는 `shutil.copyfile(...)`로 전격 교체 (`storage/local.py`, `runner/service.py`).
  - [보완] syntax-like 규칙은 원본 line number를 보존하는 comment/string-masked 분석 view에서만 실행하고, bounded summary와 대표 snippet만 feedback에 포함한다.

## 4. 후속 변경 경계

- **R-15B**: `CLIExecutionError` stdout/stderr 수집 및 OpenSCAD 런타임 diagnostics
- **R-15C**: 오케스트레이터 실행 흐름 단일화, runtime refinement, 최종 plan 저장 시점 변경
