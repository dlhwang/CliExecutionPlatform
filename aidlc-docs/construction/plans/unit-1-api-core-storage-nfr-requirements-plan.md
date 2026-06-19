# 비기능 요구사항 정의 계획서 (Unit 1: API Core & Storage Service - NFR Requirements Plan)

본 문서는 **Unit 1: API Core & Storage Service** 개발을 위한 비기능 요구사항 정의(NFR Requirements) 수립 계획 및 핵심 질의서입니다.

---

## 1. 실행 체크리스트 (Execution Checklist)

이 계획에 따라 Unit 1의 비기능 요구사항을 도출하고 기술 스택의 세부 사항을 확정합니다.

### 기획 및 질의 단계 (Planning & Questions)
- [x] **Step 1**: Unit 1 기능 설계 및 기획 결과 분석
- [x] **Step 2**: 비기능 요구사항 정의 계획서 작성 및 핵심 질문 임베드 (`unit-1-api-core-storage-nfr-requirements-plan.md` 작성 완료)
- [x] **Step 3**: 사용자 답변 수집 및 모호성 분석 (완료)
- [x] **Step 4**: 비기능 요구사항 정의 계획안에 대한 명시적 승인 획득 (완료)

### 상세 정의 단계 (Detailed Requirements Phase)
- [x] **Step 5**: 비기능 요구사항 정의서 생성 (`nfr-requirements.md`)
  * 성능, 보안, 가용성, 신뢰성 요건 구체화
- [x] **Step 6**: 기술 스택 결정서 생성 (`tech-stack-decisions.md`)
  * FastAPI, SQLAlchemy ORM 및 DB Connection Pool 세부 설정값 정의
- [x] **Step 7**: 비기능 요구사항 최종 산출물에 대한 명시적 승인 획득 (완료)

---

## 2. 비기능 요구사항 정의 단계 질의사항 (NFR Questions)

Unit 1의 비기능적 아키텍처 결정을 위해 아래 질문들에 대한 답변을 선택하거나 작성해 주시기 바랍니다.

### 질문 2.1: 데이터베이스 커넥션 풀(Connection Pool) 관리 정책
FastAPI와 PostgreSQL(SQLAlchemy) 연동 시, 동시 요청 처리를 위한 커넥션 풀의 크기와 메커니즘을 어떻게 설정하겠습니까?
- **A) 표준 풀 크기 적용 (Min: 5, Max: 20, Timeout: 30초)**: 일반적인 MVP 서비스 수준으로 구성하며 리소스 낭비를 최소화함. (추천)
- **B) 보수적 커넥션 풀 (Min: 2, Max: 5)**: 로컬 테스트 및 저사양 DB 인스턴스에 최적화하여 오버헤드를 막음.
- **C) 동적 오토스케일링 풀**: 외부 커넥션 풀러(PgBouncer 등) 설정을 전제로 한 아키텍처 고려. (현재 단계선 다소 복잡)
- **X) 기타**

[Answer]: B

---

### 질문 2.2: 임시 작업 공간(Workspace) 자동 정리 및 보존 기간 정책
작업(Job)이 완료(`COMPLETED`) 또는 실패(`FAILED`)한 직후, 로컬 호스트의 임시 작업 영역(`.workspaces/jobs/{job_id}/`)을 어떻게 관리하시겠습니까?
- **A) 즉시 자동 삭제**: 디스크 공간 확보 및 프라이버시 보호를 위해 완료/실패 즉시 삭제. (추천)
- **B) 일정 기간 보존 후 배치 삭제 (예: 24시간)**: 디버깅 및 분석을 위해 24시간 동안 유지한 후 백그라운드 스케줄러로 일괄 정리. (디버깅에 용이함)
- **C) 실패 건만 영구 보존 / 성공 건 즉시 삭제**: 실패 원인 분석을 위해 에러가 발생한 Workspace만 남겨둠.
- **X) 기타**

[Answer]: A

---

### 질문 2.3: API 성능 지연시간(Latency) 목표 설정
비동기 작업 실행의 진입점이 되는 `POST /api/v1/jobs` 요청의 동기 응답 반환 및 Workspace 물리 디렉토리 생성에 대한 목표 지연시간(Latency Baseline)은 얼마로 정의하겠습니까?
- **A) P95 기준 200ms 이하**: 백그라운드 태스크로 이관하기 때문에 생성 및 응답은 초고속으로 완료되어야 함. (추천)
- **B) P95 기준 500ms 이하**: 데이터베이스 커넥션 및 물리 폴더 생성 시의 IO 대기 시간을 고려하여 조금 넉넉히 설정.
- **X) 기타**

[Answer]: B

---

### 질문 2.4: Job 생성 API 호출 속도 제한 (Rate Limiting)
LLM API 호출 및 OpenSCAD 렌더링은 리소스 소모가 큰 작업입니다. 악의적 호출이나 무한 루프 반복 요청을 막기 위해 Job 생성 API에 속도 제한(Rate Limiting) 정책을 도입하시겠습니까?
- **A) MVP 수준 기본 Rate Limiter 탑재**: 단일 IP당 분당 최대 10회 생성으로 제한 (FastAPI-Limiter 등의 라이브러리 활용) - (추천)
- **B) 속도 제한 없음 (로컬 테스트 목적)**: MVP 단계에서는 제한 장치를 두지 않고 자유롭게 테스트함.
- **X) 기타**

[Answer]: A
