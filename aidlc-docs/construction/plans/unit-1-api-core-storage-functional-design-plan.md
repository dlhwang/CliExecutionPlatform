# 기능 설계 계획서 (Unit 1: API Core & Storage Service - Functional Design Plan) - 답변 완료

본 문서는 **Unit 1: API Core & Storage Service** 개발을 위한 상세 기능 설계(Functional Design) 수립 계획 및 핵심 질의서입니다.

---

## 1. 실행 체크리스트 (Execution Checklist)

이 계획에 따라 Unit 1의 기능 설계를 진행하고 산출물을 생성합니다.

### 기획 및 질의 단계 (Planning & Questions)
- [x] **Step 1**: Unit 1 컨텍스트 분석 (assigned stories: S-1, S-4 및 R-1, R-5)
- [x] **Step 2**: 기능 설계 계획서 작성 및 핵심 질문 임베드 (`unit-1-api-core-storage-functional-design-plan.md` 작성 완료)
- [x] **Step 3**: 사용자 답변 수집 및 모호성 분석 (완료)
- [x] **Step 4**: 기능 설계 계획안에 대한 명시적 승인 획득 (완료)

### 상세 설계 단계 (Detailed Design Phase)
- [x] **Step 5**: 비즈니스 논리 모델 생성 (`business-logic-model.md`)
  - [x] Job 생성 및 Workspace 초기화 라이프사이클의 논리적 흐름 명세
- [x] **Step 6**: 도메인 엔티티 정의서 생성 (`domain-entities.md`)
  - [x] PostgreSQL 테이블에 매핑될 Job 및 Event Log 엔티티 데이터 구조 정의
- [x] **Step 7**: 비즈니스 규칙 및 검증 규칙서 생성 (`business-rules.md`)
  - [x] Workspace 디렉토리 생성 범위 및 에러 핸들링 정책 수립
- [x] **Step 8**: 기능 설계 최종 산출물에 대한 명시적 승인 획득 (완료)

---

## 2. 기능 설계 단계 질의사항 (Clarification Questions)

Unit 1의 데이터 모델 및 파일 저장 비즈니스 규칙을 확정하기 위해 아래 질문들에 답변해 주시기 바랍니다.

### 질문 2.1: Job 테이블과 LLM Action Plan 저장 구조
Job의 생애주기 관리 중 LLM이 생성한 최종 Action Plan(JSON)을 데이터베이스에 어떻게 보존하시겠습니까?
- **A) Job 테이블 내 Pydantic JSON 컬럼으로 통합 보존**: `jobs` 테이블에 JSON 필드(또는 TEXT 필드)를 추가하여 LLM Action Plan 전체를 단일 행 내에 포함시킴. (구조가 단순함)
- **B) 별도의 Action Plan 테이블 분리**: `job_action_plans` 테이블을 1:N 혹은 1:1 관계로 분리하여 액션 단위로 행을 구성하고 실행 상태를 개별 추적함. (복잡하지만 세부 제어 가능)
- **X) 기타**

[Answer]: A) Job 테이블 내 Pydantic JSON 컬럼으로 통합 보존 (jobs 테이블에 JSON/TEXT 필드를 추가하여 전체 액션 플랜 통합 저장) - 추천

---

### 질문 2.2: Local Workspace 물리 경로 설정 규칙
`LocalStorageService`가 서버 호스트 파일 시스템 상에 임시 작업 공간(Workspace)을 만들고 Artifact를 보관할 물리적 디렉토리 위치를 어떻게 결정하시겠습니까?
- **A) 프로젝트 루트 하위의 `.workspaces` 폴더 활용**:
  - 임시 작업 공간: `D:/workspace/CLI-Execution-Platform/.workspaces/jobs/{job_id}/`
  - 영구 Artifact 보관소: `D:/workspace/CLI-Execution-Platform/.workspaces/artifacts/{job_id}/`
- **B) 사용자 지정 OS 시스템 임시 폴더 활용**: System Temp 디렉토리를 구하여 임의 격리 폴더 생성
- **X) 기타**

[Answer]: A) 프로젝트 루트 하위의 .workspaces 폴더 활용 (.workspaces/jobs/{job_id}/ 임시 공간, .workspaces/artifacts/{job_id}/ 영구 공간 분리) - 추천

---

### 질문 2.3: API 표준 에러 응답 형식 및 정책
존재하지 않는 Job ID를 조회하거나 Artifact를 요청했을 때 API Core가 반환할 HTTP 표준 오류 응답 구조를 정의해 주십시오.
- **A) 표준 REST Error Schema**: HTTP 404 Status Code와 함께 아래 형태 반환
  ```json
  {"status": "error", "code": "NOT_FOUND", "message": "Job {job_id} not found."}
  ```
- **B) FastAPI 기본 HTTPDetail 응답**: HTTP 404 Status Code와 함께 단순 디테일 텍스트 반환
  ```json
  {"detail": "Job not found"}
  ```
- **X) 기타**

[Answer]: A) 표준 REST Error Schema (HTTP 404 와 함께 status, code, message 필드가 포함된 JSON 반환) - 추천
