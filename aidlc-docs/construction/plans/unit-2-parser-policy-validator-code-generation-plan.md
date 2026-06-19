# 코드 생성 계획서 (Unit 2: Parser & Policy Validator Service - Code Generation Plan)

본 문서는 **Unit 2: Parser & Policy Validator Service**의 애플리케이션 코드 및 테스트 코드를 구현하기 위한 상세 계획서입니다. 본 계획안은 코드 생성의 기준점(Single Source of Truth)으로 작동합니다.

---

## 1. 구현 컨텍스트 및 의존성 (Context & Dependencies)

* **대상 개발 유닛**: Unit 2: LLM Plan Parser & Validator
* **적용 범위**:
  - Pydantic 2.x 다형성 Discriminator 스키마 구성 (`llm/schemas.py`)
  - Markdown JSON 추출 및 커스텀 예외 던지는 파서 구현 (`llm/parser.py`)
  - 경로 Traversal, 심볼릭링크, 절대경로, 툴 화이트리스트(openscad) 보안 검증 및 동기식 DB 감사 기록 적재기 구현 (`llm/validator.py`)
* **의존성 대상**: Unit 1 (database.py, jobs/models.py, requirements.txt 등)
* **구현 패키지 구조**: `llm/` 패키지 하위 구현

---

## 2. 스토리 추적성 및 검증 계획 (Story Traceability & Testing)

본 유닛은 다음 사용자 스토리를 구현하고 검증합니다.

### 2.1 대상 스토리 매핑
* **Story S-6: LLM Action Plan 파싱 및 유효성 검증**
  - **인수 기준**: LLM이 반환하는 Markdown 혼합 응답에서 JSON 액션 플랜을 파싱하고, Pydantic 모델로 정밀 매핑 검증. 비인가 경로(`../`, `\\`), 절대경로, 심볼릭링크, 허용되지 않는 외부 도구 실행 시도 감지 시 `PermissionError`를 내고 DB `event_logs` 테이블에 `SECURITY_ALERT` 타입 감사 로그를 동기식으로 즉시 적재함.

### 2.2 테스트 검증 시나리오 및 파일 스펙
* **테스트 파일 경로**: `tests/test_unit_2.py`
* **주요 테스트 시나리오 (Assertions)**:
  1. **Markdown 내 JSON 추출 성공 검증 (`test_json_extraction_success`)**:
     - ` ```json ... ``` ` 마크다운 코드 블록 내부의 액션 JSON 리스트 파싱 성공 검증.
     - Fallback 처리: 코드 블록 없이 첫 `[` 와 마지막 `]` 사이에 JSON이 섞인 텍스트 파싱 성공 검증.
  2. **JSON 구문 문법 오류 시 재시도 예외 검증 (`test_parser_retryable_exception`)**:
     - 괄호 누락 등 문법이 깨진 JSON 응답 주입 시 `LLMPlanRetryableException`이 유발되는지 검증.
     - 예외 객체 내부에 `error_message`, `raw_content`, `error_position` 속성이 정상 적재되어 있는지 확인.
  3. **Pydantic 스키마 검증 실패 검증 (`test_parser_validation_exception`)**:
     - `action` 명 오타 및 필수 필드 누락 시 `LLMPlanValidationError` 예외 유발 검증.
  4. **경로 침투 및 심볼릭링크 차단과 DB 감사 적재 검증 (`test_security_validator_path_protection`)**:
     - `../` 및 `..\\` 상대경로 이탈 시도 시 `LLMPlanValidationError` (HTTP 403 / FORBIDDEN_ACCESS) 차단 검증.
     - 절대경로 사용 및 심볼릭링크 탐색 시 즉시 차단 및 `PermissionError` 유발 검증.
     - 위 보안 정책 위반 상황 발생 시, 실제 DB `event_logs` 테이블에 `SECURITY_ALERT` 타입 로그가 동기식으로 INSERT 되는지 세션 조회 확인.
  5. **도구 화이트리스트 차단 검증 (`test_security_validator_tool_whitelist`)**:
     - `RUN_TOOL` 액션 시 `openscad` (대소문자 무관) 외에 `sh`, `bash`, `rm` 등 허용되지 않은 명령 유입 시 즉각 차단 검증.

---

## 3. 세부 코드 생성 순서 (Numbered Implementation Steps)

모든 작업은 아래의 번호 순서에 따라 차례대로 진행되며, 완료 시마다 체크박스 `[x]`가 업데이트됩니다.

### 1단계: 패키지 모듈 뼈대 및 Pydantic 스키마 구현
- [x] **Step 1**: `llm/schemas.py` 생성 (`CreateDirectoryAction`, `WriteFileAction`, `RunToolAction`, `CreateArtifactAction` 개별 스키마 및 `ActionPlan` 다형성 유니온 정의)
- [x] **Step 2**: `llm/parser.py` 내 커스텀 예외 클래스 (`LLMPlanException`, `LLMPlanRetryableException`, `LLMPlanValidationError`) 정의

### 2단계: 파서 및 보안 검증기 구현
- [x] **Step 3**: `llm/parser.py` 내 `ActionPlanParser` 클래스 및 Markdown JSON Fallback 정제 로직 구현
- [x] **Step 4**: `llm/validator.py` 내 `SecurityPolicyValidator` 클래스 구현 (절대/상대 경로, Symlink, openscad 툴 검증 및 DB `event_logs` 동기 INSERT 포함)

### 3단계: 테스트 코드 작성 및 검증
- [x] **Step 5**: `tests/test_unit_2.py` 생성 (2.2절에 기술된 5종의 세부 통합 검증 케이스 작성)
- [x] **Step 6**: Pytest 명령어 가동을 통해 구현물의 모든 비기능/기능 테스트 통과 증명

---

## 4. 완료 조건 (Completion Criteria)
1. `tests/test_unit_2.py` 내의 모든 단위/통합 테스트가 에러 없이 성공 패스.
2. S-6 스토리에 명시된 Markdown 추출 유연성 및 강력한 경로/툴 차단 보안과 DB 로그 적재 정책이 완벽히 준수됨.
