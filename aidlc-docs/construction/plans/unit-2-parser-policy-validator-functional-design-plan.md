# 기능 설계 계획서 (Unit 2: Parser & Policy Validator Service - Functional Design Plan)

본 문서는 **Unit 2: Parser & Policy Validator Service**의 상세 기능 설계를 수행하기 위한 세부 계획서 및 의사결정을 위한 질문지입니다.

---

## 1. 개요 및 목적 (Goal Description)

* **대상 개발 유닛**: Unit 2: LLM Plan Parser & Validator
* **목적**: LLM이 반환하는 Markdown 혼합 응답에서 JSON 액션 플랜(Action Plan)을 파싱하고, Pydantic을 통해 형식을 엄격히 검증하며, 악성 경로 및 비인가 CLI 실행 시도를 철저히 차단하는 비즈니스 논리와 보안 규칙을 설계합니다.
* **주요 요건**:
  - LLM 마크다운 블록 내 JSON 추출 및 Pydantic 매핑 (`ActionPlanParser`).
  - 상대경로 탈출(`../`), 절대경로, 심볼릭 링크, 시스템 경로 차단 및 화이트리스트 툴 검증 (`SecurityPolicyValidator`).

---

## 2. 의사결정을 위한 공개 질문지 (Open Questions)

> [!IMPORTANT]
> **Unit 2의 비즈니스 논리 설계를 위해 아래 질문에 답변해 주십시오.**  
> 각 질문에 대해 적절한 옵션을 선택하거나 세부 사항을 기재해 주십시오.

### 질문 1. LLM 액션 플랜 JSON 내 각 액션별 필드 규격
LLM이 생성하는 JSON 액션 목록에서 각 액션 타입(`CREATE_DIRECTORY`, `WRITE_FILE`, `RUN_TOOL`, `CREATE_ARTIFACT`)별로 요구되는 필수 및 선택 필드를 어떻게 정의할까요?
* **옵션 A (기본 필드 세트)**: 
  - `CREATE_DIRECTORY`: `path` (str)
  - `WRITE_FILE`: `path` (str), `content` (str)
  - `RUN_TOOL`: `tool_name` (str), `args` (List[str])
  - `CREATE_ARTIFACT`: `path` (str)
* **옵션 B (추가 제약 포함)**: 옵션 A에 더해 파일 쓰기 모드(`mode`: "text" | "binary")나 실행 제한 옵션 등 추가 메타데이터 필드를 확장 정의
* **선택**: 
[Answer]:  A

### 질문 2. Markdown 내 JSON 추출 파싱 전략
LLM 응답 텍스트에 마크다운 문법(예: ` ```json ... ``` `) 및 설명 글이 혼합되어 있을 때, JSON 문자열을 추출하는 파싱 전략은 어떻게 설계할까요?
* **옵션 A (정규식 기반 추출)**: `(?s)```json\s*(.*?)\s*``` ` 정규식을 우선 적용하고, 매칭에 실패할 경우 텍스트 전체에서 첫 번째 `[` 와 마지막 `]` 사이의 유효한 JSON 배열 문자열을 찾아서 파싱을 시도하는 복합(Fallback) 파서 구현. (가장 안정적)
* **옵션 B (엄격한 마크다운 블록 파싱)**: 오직 ` ```json ` 및 ` ``` ` 코드 블록으로 명확하게 감싸진 블록만 찾아서 추출하며, 그 외 텍스트가 섞여있을 시 즉시 파싱 에러를 유발.
* **선택**: 
[Answer]: A

### 질문 3. RUN_TOOL의 CLI 실행 허용 화이트리스트 정책
보안상 `RUN_TOOL` 액션에서 실행할 수 있는 외부 도구명을 엄격히 통제해야 합니다. MVP 단계에서 허용할 툴 화이트리스트 정책은 어떻게 구성할까요?
* **옵션 A (OpenSCAD 단일 허용)**: 오직 `openscad` (대소문자 무관하게 정규화) 툴명만 허용하며, 그 외의 도구명은 즉시 정책 위반(`FORBIDDEN_ACCESS`) 에러를 냅니다.
* **옵션 B (추가 도구 목록 사전 정의)**: 향후 연동을 고려하여 `openscad` 외에 `mermaid`, `plantuml` 등 지정된 목록까지 화이트리스트에 등록해 두고 통제합니다.
* **선택**: 
[Answer]: A

### 질문 4. 보안 경로 검증 시 심볼릭 링크 및 절대경로 차단 방식
경로 검증 시, `relative_path`에 대한 단순 텍스트 검사(`../` 등) 외에 물리적 디렉토리 검증에서 심볼릭 링크(Symbolic Link)와 절대 경로에 대해 어떻게 예외 처리를 수행할까요?
* **옵션 A (엄격한 예외 트리거)**: 파일/폴더 생성 및 조회 요청 경로를 resolve하기 전에 절대경로로 시작하거나, 물리 경로가 존재할 경우 `is_symlink()` 여부를 체크하여 심볼릭 링크인 경우 즉시 `PermissionError`를 던집니다.
* **옵션 B (단순 resolve 및 is_relative_to 검사)**: 심볼릭 링크 여부 검사 없이 `Path.resolve()` 이후 `is_relative_to(base_dir)`에 속하는지만 검증합니다.
* **선택**: 
[Answer]: A

---

## 3. 기능 설계 세부 수행 계획 (Functional Design Checklist)

본 계획서 승인 이후 순차적으로 수행할 상세 Checklist입니다.

- [x] **Step 1**: Unit 2 비즈니스 논리 모델 설계서 생성 (`business-logic-model.md`)
  - 마크다운 파싱 가공 알고리즘 순서도 명세
  - Pydantic Action Plan 유효성 체크 프로세스 흐름 명세
- [x] **Step 2**: 도메인 엔티티 정의서 생성 (`domain-entities.md`)
  - Pydantic Action 데이터 타입 및 BaseAction 스키마 정의
  - 각 Action별 필드 정의
- [x] **Step 3**: 보안 및 검증 비즈니스 규칙서 생성 (`business-rules.md`)
  - Traversal 차단, 화이트리스트 제약 조건 표
  - 예외 발생 시 표준 REST API 에러 매핑 정책 구체화
