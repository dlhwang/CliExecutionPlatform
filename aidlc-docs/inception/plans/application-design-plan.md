# 애플리케이션 설계 계획서 (Application Design Plan) - 답변 완료

본 문서는 **LLM 기반 Workspace CLI Execution Platform**의 상위 컴포넌트 설계 및 서비스 레이어 아키텍처를 정의하기 위한 기획서입니다.

---

## 1. 실행 체크리스트 (Execution Checklist)

이 계획에 따라 애플리케이션 설계를 진행하고 산출물을 생성합니다.

### 기획 및 질의 단계 (Planning & Questions)
- [x] **Step 1**: 애플리케이션 설계 지침 분석 및 범위 확정
- [x] **Step 2**: 설계 계획서 작성 및 핵심 설계 질의 임베드 (`application-design-plan.md` 작성 완료)
- [x] **Step 3**: 사용자 답변 수집 및 모호성 분석 (완료)
- [x] **Step 4**: 설계 기획안에 대한 명시적 승인 획득 (완료: 2026-06-18T17:29:20+09:00)

### 상세 설계 단계 (Detailed Design Phase)
- [x] **Step 5**: 컴포넌트 정의서 생성 (`components.md`) (완료)
  - [x] 주요 기능 컴포넌트(API, Validator, Executor, SSE, Storage) 식별 및 역할 정의 (완료)
- [x] **Step 6**: 컴포넌트 메서드 및 인터페이스 정의서 생성 (`component-methods.md`) (완료)
  - [x] 주요 메서드 시그니처 및 입출력 타입 정의 (완료)
- [x] **Step 7**: 서비스 레이어 오케스트레이션 정의서 생성 (`services.md`) (완료)
  - [x] Job 라이프사이클 처리 서비스 흐름 기술 (완료)
- [x] **Step 8**: 컴포넌트 의존성 및 데이터 흐름 정의서 생성 (`component-dependency.md`) (완료)
  - [x] 컴포넌트 간 호출 구조 및 데이터 흐름 다이어그램 작성 (완료)
- [x] **Step 9**: 설계 통합 문서 생성 (`application-design.md`) (완료)
  - [x] 개별 설계 문서를 하나로 취합한 종합 설계 문서 작성 (완료)
- [ ] **Step 10**: 애플리케이션 설계 산출물에 대한 명시적 승인 획득 (대기 중)

---

## 2. 설계 단계 질의사항 (Clarification Questions)

애플리케이션 아키텍처를 명확히 설계하기 위해 아래의 핵심 질문들에 답변해 주시기 바랍니다.

### 질문 2.1: 백엔드 모듈 아키텍처 구조
FastAPI 백엔드의 패키지/폴더 구조를 설계할 때, 어떤 방식을 더 선호하십니까?
- **A) 레이어드 아키텍처 (Layered)**: `routers/`, `services/`, `repositories/`, `models/` 처럼 기술적 역할 단위로 폴더를 분류하여 구성 (전형적인 소규모 API 구조)
- **B) 도메인/기능 중심 아키텍처 (Domain-driven/Feature-based)**: `jobs/`, `artifacts/`, `sse/`, `storage/` 처럼 비즈니스 기능(도메인) 단위로 폴더를 분리하고 그 안에 router, service, model을 각각 모아 구성 (도구 확장성에 유리)
- **X) 기타**

[Answer]: B) 옵션 B: 도메인/기능 중심 아키텍처 (jobs/, artifacts/, sse/, storage/ 도메인 단위로 폴더 분류하여 확장성 확보)

---

### 질문 2.2: LLM Action Plan 검증기의 설계 경계
LLM이 반환하는 JSON Action Plan의 파싱과 검증을 담당하는 컴포넌트의 구성 방식에 대해 어떤 설계를 선호하십니까?
- **A) 단일 검증 서비스 (Single Validator Component)**: `ActionPlanService` 내부에서 JSON 파싱과 경로 traversal 검증, 액션 타입 검증을 모두 함께 수행하여 컴포넌트 개수를 최소화
- **B) 역할 분리 구조 (Parser & Policy Validator)**: JSON 구조체 검증(Pydantic model 이용)을 수행하는 `ActionPlanParser`와 파일 경로 Traversal 검증 및 CLI 인수 정책을 전담하는 보안 정책 검증기 `SecurityPolicyValidator`로 모듈을 분리하여 보안 가독성 높임 (보안 가독성 높음)
- **X) 기타**

[Answer]: B) 옵션 B: 역할 분리 구조 (Pydantic 기반 파서 ActionPlanParser와 보안 및 경로 traversal 검증을 수행하는 SecurityPolicyValidator로 모듈 분리)

---

### 질문 2.3: Storage 추상화 인터페이스
최종 산출물 및 작업 파일을 다루는 `StorageService` 인터페이스의 핵심 API를 아래 설계안 A와 B 중 어떤 방향에 가깝게 설계할까요?
- **A) 단순 파일 I/O 추상화**:
  - `save_file(job_id, relative_path, file_content)`
  - `read_file(job_id, relative_path) -> bytes`
  - `get_download_url(job_id, relative_path) -> str`
- **B) 아티팩트 단위 저장 기능 결합**:
  - `store_job_artifact(job_id, artifact_type, file_content)`
  - `get_artifact_stream(job_id, file_name) -> Stream`
  - `clean_workspace(job_id)` (Job 완료/실패 시 정리 기능 포함)
- **X) 기타**

[Answer]: B) 옵션 B: 아티팩트 단위 저장 기능 결합 (store_job_artifact, clean_workspace 등 비즈니스 요구에 밀접한 인터페이스 결합)

---

### 질문 2.4: 비동기 Job 실행과 SSE 로그 전달 오케스트레이션
FastAPI에서 사용자가 설계 요청을 하면 비동기 백그라운드로 Job이 실행되는데, 로그 수집 및 SSE 연동의 오케스트레이션을 어떻게 구성할까요?
- **A) Local Memory Event Queue + DB Logging**: Job이 실행될 때 발생하는 로그를 메모리 내 Queue에 즉시 push하고, SSE 리스너가 이 큐를 리독하여 스트리밍하며, 백그라운드 스레드가 이 큐에서 읽어 DB에 영속화함. (실시간성 우수, 단 복잡함)
- **B) Direct DB Log Insertion + SQL Polling**: Job Runner는 모든 진행 상황과 CLI 로그를 DB `event_logs` 테이블에 즉시 INSERT만 하고, SSE 스트림 핸들러는 주기적으로(예: 0.1~0.5초 간격) DB를 조회(Polling)하여 최신 로그를 클라이언트에 전송함. (단순하며 YAGNI 원칙 준수)
- **X) 기타**

[Answer]: B) 옵션 B: Direct DB Log Insertion + SQL Polling (Job Runner는 모든 로그를 DB에 즉시 INSERT하고, SSE 핸들러는 DB를 0.5초 주기로 폴링하여 클라이언트에 스트리밍) - YAGNI 원칙 부합
