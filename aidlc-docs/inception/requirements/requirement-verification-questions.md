# Requirement Verification Questions - Hotfix Cycle (R-15)

본 문서는 OpenSCAD 코드 생성 제약 조건 강화 및 SCAD 정적 검증 기능 추가에 관한 구체적인 설계 세부사항을 확정하기 위한 질문지입니다. 각 항목의 [Answer]: 태그 뒤에 직접 답변을 입력해 주시기 바랍니다.

---

### Q1. SCAD 파일의 정적 검증(Validation) 수행 시점

LLM이 생성한 Scad 파일에 대한 정적 검증을 애플리케이션의 어느 생명주기(Lifecycle) 시점에 수행할지 결정해야 합니다.

- **A) [추천] LLM Action Plan 파싱 및 검증 단계 (llm/validator.py 등)**:
  LLM이 `WRITE_FILE` 또는 `RUN_TOOL` 액션 등을 담은 Plan을 반환하여 파싱하는 시점에 미리 scad 구문 오류(v.x, 싱글 쿼트 등)를 검증합니다. 실패 시 `LLMPlanValidationError` 등을 발생시켜 오케스트레이터가 이를 감지하고 LLM에 피드백을 주어 refinement 루프를 통해 코드를 자동 재작성하도록 유도할 수 있습니다.
- **B) CLI 실행 직전 단계 (runner/service.py 등)**:
  `run_tool`이 실행되기 직전, `/tmp` 격리 실행 디렉토리에 복사하기 전에 검증을 수행합니다. 위반 시 `CLIExecutionError` 또는 validation 예외를 발생시키고 실행을 즉각 중단합니다. (LLM의 자동 refinement 재시도보다는 즉각적인 실행 실패에 포커싱)
- **C) 기타 (답변에 구체적인 내용을 작성해 주세요)**

[Answer]: A

---

### Q2. SCAD 구문 정적 검증 규칙의 구체적 대상

정적 검증을 수행할 때 필터링할 구문 오류의 구체적인 패턴 범위입니다. (복수 선택 가능)

- **A) [추천] 사용자 제시 3대 규칙 세트 모두 적용**:
  1. `v.x`, `v.y`, `v.z` 등 벡터 속성 접근 차단 (반드시 `v[0]`, `v[1]`, `v[2]` 인덱스만 허용)
  2. 싱글 쿼트 `'` 사용 차단 (더블 쿼트만 허용)
  3. 삼각함수 결과값에 대한 `180 / PI` 또는 `PI / 180` 등의 수식 검출 및 차단 (OpenSCAD는 기본적으로 degrees 단위이므로 라디안 변환 불필요)
- **B) 부분 적용**: (상기 3가지 중 특정 패턴만 적용하고 싶을 시 선택하고, [Answer]란에 기술해 주세요)
- **C) 기타 추가 규칙 반영**: (마크다운 코드 펜스 등 추가적인 검증 규칙을 포함하고 싶을 경우 선택 및 기술)

[Answer]: A, C
추가 적용 대상:
- Markdown code fence 차단: scad, openscad, ``` 등
- 설명문/prose로 시작하는 출력 차단: Here is, The following, 아래는, 다음은 등
- 빈 SCAD 파일 차단
- 최소 OpenSCAD 구조 검증: module, polyhedron, cube, sphere, difference, union = 등 OpenSCAD 구성 요소가 전혀 없는 경우 차단

단, 이번 Hotfix 범위에서는 OpenSCAD 전체 문법 파서를 구현하지 않고, 반복적으로 발생한 LLM 생성 오류를 막는 lightweight static validation으로 제한합니다.

---

### Q3. 정적 검증 실패 시 예외 처리 및 오케스트레이션 흐름

scad 검증기(Validator)에서 오류가 발견되었을 때의 예외 처리 방식입니다.

- **A) [추천] LLMPlanValidationError 발생 (Refinement Loop 유도)**:
  에러를 오케스트레이터가 잡아서 LLM에게 에러 메시지와 함께 refinement를 다시 요청(최대 2회 재시도)하여, 올바른 OpenSCAD 문법의 코드를 생성하도록 유도합니다.
- **B) CLIExecutionValidationError 발생 (즉시 실패 처리)**:
  오케스트레이션을 더 재시도하지 않고 해당 Job을 즉시 `FAILED` 상태로 변환합니다.
- **C) 기타 (답변에 구체적인 내용을 작성해 주세요)**

[Answer]: A

---

### Q4. Security Baseline 확장 옵션 적용 여부
이 핫픽스 개발 과정에 'Security Baseline' 확장 규칙을 반영하여 보안 관련 추가 통제를 적용할지 결정합니다.

- **A) No (기존 결정 유지 - 비활성화)**
- **B) Yes (활성화)**

[Answer]: A

---

### Q5. Property-Based Testing 확장 옵션 적용 여부
scad 검증기 등에 대하여 Property-Based Testing(PBT) 기법을 사용한 테스트 생성을 수행할지 결정합니다.

- **A) No (기존 결정 유지 - 비활성화)**
- **B) Yes (활성화)**

[Answer]: A

---
