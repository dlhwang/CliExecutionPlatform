# 작업 단위 생성 계획서 (Unit of Work Plan) - 답변 완료

본 문서는 **LLM 기반 Workspace CLI Execution Platform** 개발 작업을 독립적인 개발 단위(Unit of Work)로 세분화하고 일정을 수립하기 위한 계획서입니다.

---

## 1. 실행 체크리스트 (Execution Checklist)

이 계획에 따라 시스템을 개발 단위(Unit)로 분할하고 관련 산출물을 생성합니다.

### 기획 및 질의 단계 (Planning & Questions)
- [x] **Step 1**: 작업 분할 규칙 분석 및 범위 확정
- [x] **Step 2**: 작업 단위 계획서 작성 및 핵심 질문 임베드 (`unit-of-work-plan.md` 작성 완료)
- [x] **Step 3**: 사용자 답변 수집 및 모호성 분석 (완료)
- [x] **Step 4**: 작업 단위 기획안에 대한 명시적 승인 획득 (완료: 2026-06-18T17:32:32+09:00)

### 작업 단위 명세 단계 (Generation Phase)
- [x] **Step 5**: 작업 단위 정의서 생성 (`unit-of-work.md`) (완료)
  - [x] 각 개발 유닛(Unit 1~5)의 역할과 코드 배치를 기술 (완료)
- [x] **Step 6**: 작업 단위 간 의존성 매트릭스 생성 (`unit-of-work-dependency.md`) (완료)
  - [x] 유닛 간 빌드/런타임 의존 관계 정의 (완료)
- [x] **Step 7**: 작업 단위별 사용자 스토리 매핑 문서 생성 (`unit-of-work-story-map.md`) (완료)
  - [x] 작성된 7개 사용자 스토리를 각 유닛 백로그로 연결 (완료)
- [ ] **Step 8**: 작업 단위 설계 결과물에 대한 최종 승인 획득 (대기 중)

---

## 2. 작업 단위 분할 제안 (Proposed Units of Work)

본 MVP 시스템은 단일 FastAPI 애플리케이션 형태의 논리적 모듈 구조를 가지며, 다음과 같은 5개의 독립된 개발 단위(Unit of Work)로 분리하여 차례대로 구현하는 것을 제안합니다.

1. **Unit 1: API Core & Storage Service**
   - **범위**: FastAPI 기본 서버 설정, PostgreSQL 데이터베이스 연결 및 마이그레이션 스키마 정의(Job 및 Event Log 테이블), `StorageService` 추상 인터페이스 및 로컬 파일 기반 `LocalStorageService` 구현.
   - **스토리 매핑**: Story S-1(Job 요청), Story S-4(Artifact 다운로드), Requirement R-1, R-5.
2. **Unit 2: LLM Plan Parser & Validator**
   - **범위**: LLM의 응답에서 JSON Action Plan을 파싱하는 `ActionPlanParser`, 파일 경로 Traversal 방지(`../` 차단) 및 툴 호출 화이트리스트 검사를 전담하는 `SecurityPolicyValidator` 구현 및 단위 테스트 작성.
   - **스토리 매핑**: Story S-6(Plan 파싱 및 유효성 검사), Requirement R-2.
3. **Unit 3: CLI Execution Runner**
   - **범위**: OpenSCAD CLI 실행을 담당하는 `CLIExecutionRunner`, `subprocess.Popen`을 통한 인자 매핑, 타임아웃(30초) 리소스 제약 통제 및 예외 처리 구현.
   - **스토리 매핑**: Story S-7(OpenSCAD CLI 격리 실행), Requirement R-3.
4. **Unit 4: SSE Streaming & Event Catch-up**
   - **범위**: `SSEConnectionManager` 구현, 0.5초 주기의 SQL 로그 테이블 폴링 메커니즘, `Last-Event-ID` 수신 시 DB에서 누락 이벤트를 가져와 재전송(Catch-up)하는 복구 로직 구현.
   - **스토리 매핑**: Story S-2(SSE 실시간 로깅), Story S-3(SSE 스트림 복구), Requirement R-4.
5. **Unit 5: Iterative Refinement Orchestrator**
   - **범위**: API 엔드포인트와 각 컴포넌트를 비동기로 엮는 `JobOrchestratorService` 비동기 루프 완성, 이전 완료된 Job의 model.scad 파일을 복사해 와 추가 자연어 수정을 수용하는 피드백 반복 수정 시나리오 구현.
   - **스토리 매핑**: Story S-5(대화형 피드백 반복 수정).

---

## 3. 기획 단계 질의사항 (Clarification Questions)

개발 단위 분할과 코드 구조 설정을 구체화하기 위해 아래 질문들에 답변해 주시기 바랍니다.

### 질문 3.1: 작업 단위(Unit of Work) 분할 방식 동의 여부
위에 제안된 5가지 개발 단위(Unit 1 ~ Unit 5)로 작업을 분리하여 순차적으로 구현하는 방식에 동의하십니까?
- **A) 동의함**: 제안된 5대 유닛 단위로 설계/구현/테스트를 차례대로 반복 진행 (추천)
- **B) 병합 진행**: 작업을 더 단순화하기 위해 유닛 개수를 줄여 병합 구현 (예: Unit 1+5 병합 등)
- **X) 기타**

[Answer]: A) 동의함: 제안된 5대 유닛 단위로 설계/구현/테스트를 차례대로 반복 진행 (추천)

---

### 질문 3.2: 패키지/의존성 관리 도구 선정 (Greenfield)
FastAPI 프로젝트의 의존성 라이브러리(FastAPI, Pydantic, SQLAlchemy, psycopg2 등) 및 가상 환경을 관리하기 위해 어떤 도구를 사용하겠습니까?
- **A) Poetry**: 현대적인 Python 패키지/의존성 관리자 활용
- **B) PIP + Virtualenv**: 가장 보편적이고 단순한 `requirements.txt`와 venv 가상환경 구성
- **X) 기타**

[Answer]: B) 옵션 B: PIP + Virtualenv (가장 보편적이고 가벼운 requirements.txt와 venv 가상환경 구성)
