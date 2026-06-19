# 코드 생성 계획서 - Unit 5: Iterative Refinement Orchestrator

> 이 문서는 Unit 5 Code Generation의 단일 정보 출처입니다. 승인 후 아래 단계를 순서대로 실행하고 완료 즉시 체크박스를 갱신합니다.

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | Greenfield / Monolith |
| 주 애플리케이션 코드 | `D:\workspace\CLI-Execution-Platform\orchestrator\`, 기존 `jobs/`, `llm/`, `storage/`, `main.py` |
| 테스트 | `D:\workspace\CLI-Execution-Platform\tests\test_unit_5.py` |
| 마이그레이션 | `D:\workspace\CLI-Execution-Platform\migrations\001_add_parent_job_id.sql` |
| 코드 문서 | `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/code/code-summary.md` |
| 선행 유닛 | Unit 1 Job/Storage, Unit 2 Parser/Validator, Unit 3 Runner, Unit 4 SSE |

## 스토리 추적성

| 스토리 | 구현 범위 | 검증 |
|---|---|---|
| S-5 | 완료 Job 기반 refinement API와 새 자식 Job 생성 | `test_refinement_creates_child_job` |
| S-5 | `model.scad`, `design-spec.md` 상속 및 LLM 컨텍스트 전달 | `test_refinement_copies_context_and_calls_llm` |
| S-5 | 검증 플랜의 직렬 실행과 최종 상태 전이 | `test_orchestrator_executes_actions_in_order` |

## 요구사항 검증 매핑

| 요구사항 | 테스트 증거 |
|---|---|
| BR-5-3, BR-5-5 | `test_refinement_rejects_invalid_parent_or_missing_files` |
| BR-5-7, BR-5-16 | `test_job_state_transitions_and_duplicate_execution` |
| BR-5-9, NFR-5-5 | `test_llm_retry_classification_and_backoff` |
| BR-5-10, BR-5-11 | `test_plan_is_validated_before_serial_execution` |
| NFR-5-1 | `test_llm_client_uses_120_second_timeout` |
| NFR-5-2 | `test_concurrency_gate_limits_two_jobs_and_times_out_waiter` |
| NFR-5-4 | `test_context_and_response_size_limits` |
| NFR-5-6 | `test_state_and_event_commit_atomically` |
| NFR-5-7 | `test_stale_running_jobs_recovered_at_startup` |
| NFR-5-9, NFR-5-10 | `test_endpoint_security_and_secret_validation` |
| NFR-5-11 | `test_redirect_and_untrusted_plan_are_rejected` |

## Part 1: 계획 수립 체크리스트

- [x] P1: 기능 설계, NFR Requirements, NFR Design 분석
- [x] P2: 기존 Job, Parser, Validator, Runner, Storage, SSE 인터페이스 분석
- [x] P3: 생성/수정 파일과 데이터 변경 범위 확정
- [x] P4: S-5와 BR/NFR 자동화 테스트 매핑
- [x] P5: 코드 생성 계획 작성 및 승인 요청 기록
- [x] P6: 사용자 계획 승인 기록

## Part 2: 생성 단계 체크리스트

### Step 1: Job 계보 모델과 마이그레이션

- [x] `jobs/models.py`에 nullable `parent_job_id` 자기 참조 FK와 관계 추가
- [x] `jobs/schemas.py`에 refinement 요청과 `parent_job_id` 응답 필드 추가
- [x] `migrations/001_add_parent_job_id.sql` idempotent PostgreSQL 변경 스크립트 생성
- [x] 신규 SQLite metadata 생성과 기존 PostgreSQL 변경 경로 모두 문서화

### Step 2: LLM HTTP client와 재시도 계층

- [x] `llm/client.py` 생성: `LLMClient` protocol, `HttpLLMClient`, 오류 계층
- [x] shared `httpx.AsyncClient`, timeout 120초, redirect 거부 적용
- [x] streaming body 누적 5MB 제한과 UTF-8/JSON/content 추출 구현
- [x] `llm/retry.py` 생성: timeout/연결/408/429/5xx/파싱 오류 최대 2회 재시도
- [x] 1초, 2초 async backoff와 retry feedback 구현

### Step 3: Storage refinement 연산 확장

- [x] `storage/interface.py`에 안전한 파일 존재, 크기, 디렉터리 생성, Job 간 파일 복사 계약 추가
- [x] `storage/local.py`에 traversal 방어를 재사용한 구현 추가
- [x] 두 상속 파일의 합계 크기를 전체 중복 로드 없이 검증

### Step 4: Job 상태 저장소와 stale 복구

- [x] `orchestrator/repository.py` 생성: 자식 Job, 조건부 상태 전이, action plan 저장
- [x] 상태 update와 EventLog insert를 동일 트랜잭션으로 처리
- [x] `orchestrator/recovery.py` 생성: 15분 stale Job 조건부 실패 전환
- [x] 경쟁 update 시 복구 이벤트 중복 방지

### Step 5: 동시성 gate와 액션 실행기

- [x] `orchestrator/concurrency.py` 생성: semaphore 2개, 10분 wait timeout, 안전한 반환
- [x] `orchestrator/actions.py` 생성: 네 액션 타입의 순차 dispatch
- [x] 첫 액션 실패 시 중단하고 부분 Workspace 보존

### Step 6: 핵심 오케스트레이터 서비스

- [x] `orchestrator/service.py`, `orchestrator/__init__.py` 생성
- [x] `CREATED -> RUNNING -> COMPLETED/FAILED` 전체 흐름 구현
- [x] refinement 컨텍스트 복사와 LLM 요청 구성
- [x] parser 후 전체 validator 선검증, action plan 저장, 직렬 실행
- [x] 최상위 예외 처리와 안정적인 실패 코드/EventLog 기록
- [x] 중복 실행 방지와 모든 종료 경로의 semaphore 반환

### Step 7: API와 lifespan 통합

- [x] `orchestrator/config.py` 생성: 환경 설정 및 HTTPS/loopback HTTP 검증
- [x] `jobs/service.py` 확장: 부모 검증, refinement preflight, 자식 Job 생성
- [x] `jobs/router.py`에 `POST /api/v1/jobs/{previous_job_id}/refine` 추가
- [x] 기존 placeholder BackgroundTask를 실제 오케스트레이터 호출로 교체
- [x] `main.py` lifespan에 shared client 생성/close와 stale recovery 연결
- [x] API 사전 404, 409, 413 처리 및 자식 Job 미생성 검증

### Step 8: Unit 5 자동화 테스트

- [x] `tests/conftest.py`에 LLM 환경 설정과 오케스트레이터 의존성 격리 추가
- [x] `tests/test_unit_5.py` 생성
- [x] refinement 성공, 계보, 파일 상속, 직렬 액션, 상태 전이 검증
- [x] retry 분류, 120초 timeout, 1초·2초 backoff 검증
- [x] 2개 동시 실행, 세 번째 10분 timeout, 슬롯 반환 검증
- [x] 5MB 요청/응답, HTTPS/localhost, 3xx 거부 검증
- [x] 15분 stale 복구와 트랜잭션 원자성 검증
- [x] 실패 Workspace 보존과 민감정보 비노출 검증

### Step 9: 테스트와 파일 검증

- [x] Unit 5 테스트 실행 (10 passed)
- [x] 전체 pytest 실행으로 Unit 1-4 회귀 없음 확인 (45 passed)
- [x] 실패 원인 수정 후 동일 범위 재실행 (테스트 UUID 타입 오류 수정)
- [x] 모든 변경/생성 파일 UTF-8 BOM 없음 검증
- [x] `git diff --check` 통과 확인

### Step 10: 코드 요약과 완료 상태

- [x] `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/code/code-summary.md` 생성
- [x] 생성/수정 파일, 스키마 변경, 설계 결정, 테스트 결과 기록
- [x] S-5 및 BR/NFR별 테스트 증거 기록
- [x] 자동화하지 못한 항목은 N/A 사유 기록
- [x] 모든 계획 체크박스 완료 확인
- [x] `aidlc-state.md`를 Unit 5 Code Generation 승인 대기로 갱신
- [x] 표준 Code Generation 완료 메시지 제시

## 예상 파일 변경

### 신규 파일

- `orchestrator/__init__.py`
- `orchestrator/config.py`
- `orchestrator/repository.py`
- `orchestrator/recovery.py`
- `orchestrator/concurrency.py`
- `orchestrator/actions.py`
- `orchestrator/service.py`
- `llm/client.py`
- `llm/retry.py`
- `migrations/001_add_parent_job_id.sql`
- `tests/test_unit_5.py`
- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/code/code-summary.md`

### 수정 파일

- `jobs/models.py`
- `jobs/schemas.py`
- `jobs/service.py`
- `jobs/router.py`
- `storage/interface.py`
- `storage/local.py`
- `main.py`
- `tests/conftest.py`

## 제외 항목

- 외부 Queue 및 별도 worker: MVP 범위 밖
- 중단 Job 재개: stale Job은 `FAILED` 전환만 수행
- 다중 프로세스 전역 semaphore: 프로세스 로컬 제한만 적용
- 실제 외부 LLM 호출 테스트: fake client와 `httpx.MockTransport`로 대체
- 프론트엔드: Unit 5 범위 밖

## 승인 상태

- **상태**: 생성 완료, 코드 검토 승인 대기
- **승인 후 동작**: Step 1부터 Step 10까지 순차 실행
