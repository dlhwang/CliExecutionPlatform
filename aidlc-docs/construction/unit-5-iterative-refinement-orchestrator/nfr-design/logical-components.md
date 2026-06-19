# 논리 컴포넌트 - Unit 5: Iterative Refinement Orchestrator

## 컴포넌트 구성

### OrchestratorConfig

책임:

- LLM endpoint, API key, model, 실행 환경 로드
- 120초 timeout, 5MB 제한, 동시 실행 2개, 대기 10분, stale 15분 설정 제공
- 운영 HTTPS 및 개발 loopback HTTP 검증
- URL userinfo, fragment, 잘못된 scheme 거부

### LLMClient

공급자 독립 포트입니다.

- `generate_plan(request) -> str` 비동기 계약
- 오케스트레이터는 HTTP 상태나 payload 구조를 직접 알지 않음
- fake 구현으로 성공, timeout, 오류, 잘못된 응답 주입 가능

### HttpLLMClient

책임:

- lifespan shared `httpx.AsyncClient` 사용
- 내부 요청을 endpoint payload로 변환
- redirect를 따르지 않고 3xx 거부
- HTTP 상태를 retryable 또는 terminal 오류로 분류
- `BoundedResponseReader`로 body 수신
- 응답 JSON에서 `content` 텍스트 추출

### BoundedResponseReader

책임:

- streaming body의 누적 byte 계산
- 5MB 초과 즉시 중단 및 응답 close
- 제한 내 byte를 UTF-8로 decode
- `Content-Length` 사전 검사와 실제 byte 검사를 함께 적용

### LLMRetryExecutor

책임:

- 최초 호출과 최대 2회 재시도 오케스트레이션
- timeout, 연결 오류, 408, 429, 5xx, 파싱 가능 오류만 재시도
- 1초, 2초 async backoff
- 시도 횟수 EventLog 기록
- terminal 오류와 retry exhaustion을 안정적인 도메인 오류로 변환

### OrchestrationConcurrencyGate

책임:

- 프로세스 로컬 `Semaphore(2)` 소유
- 최대 10분 슬롯 대기
- 획득 전 Job을 `CREATED`로 유지
- 대기 timeout 오류 생성
- 모든 종료 경로에서 슬롯 반환

### RefinementPreflightService

책임:

- 부모 Job 존재 및 `COMPLETED` 상태 검증
- `model.scad`, `design-spec.md` 존재 검증
- 두 파일의 byte 합계가 5MB 이하인지 검증
- 검증을 통과한 경우에만 자식 Job 생성 흐름 허용
- 404, 409, 413 도메인 오류 구분

필요한 저장소 확장:

- 안전한 Workspace 파일 존재 여부 확인
- 파일 크기 조회 또는 제한된 byte 읽기
- 부모 파일을 자식 Workspace로 복사

### JobStateRepository

책임:

- `CREATED`에서 `RUNNING` 조건부 전이
- `RUNNING`에서 `COMPLETED` 또는 `FAILED` 조건부 전이
- 상태 전이와 EventLog insert의 단일 트랜잭션 보장
- 검증된 action plan 저장
- parent-child Job 관계 조회 및 생성

### StaleJobRecoveryService

책임:

- 시작 시 15분 이상 stale `RUNNING` Job 검색
- Job별 조건부 `FAILED` update
- 동일 트랜잭션에서 복구 EventLog insert
- 중복 또는 경쟁 update 무시
- 처리 건수 구조화 로그 기록

### ActionExecutor

책임:

- 검증된 액션을 순서대로 dispatch
- `CREATE_DIRECTORY`를 Storage에 위임
- `WRITE_FILE`을 Storage에 위임
- `RUN_TOOL`을 `CLIExecutionRunner`에 위임
- `CREATE_ARTIFACT`를 Storage에 위임
- 첫 실패에서 실행 중단

### JobOrchestratorService

책임:

- concurrency gate 획득
- 상태를 `RUNNING`으로 조건부 전이
- 선택적 부모 컨텍스트 복사 및 LLM 요청 구성
- LLM retry executor 호출
- parser와 validator를 통한 전체 플랜 선검증
- action plan 저장 및 ActionExecutor 호출
- 최종 `COMPLETED` 또는 `FAILED` 전이
- 최상위 예외 포착과 슬롯 반환

### LifespanResourceProvider

책임:

- 애플리케이션 시작 시 설정 검증
- shared `httpx.AsyncClient` 생성
- stale recovery 실행
- 애플리케이션 종료 시 HTTP client close
- 테스트에서 mock transport와 대체 provider 주입

## 처리 순서

### refinement 접수

1. Router가 `RefinementPreflightService`를 호출합니다.
2. 부모 상태, 파일 존재, 합계 5MB 제한을 확인합니다.
3. 검증 실패 시 자식 Job 없이 404, 409 또는 413을 반환합니다.
4. 검증 성공 시 `parent_job_id`가 지정된 자식 Job과 Workspace를 만듭니다.
5. BackgroundTask에 `job_id`를 전달하고 즉시 201을 반환합니다.

### 백그라운드 실행

1. `JobOrchestratorService`가 최대 10분간 concurrency slot을 기다립니다.
2. timeout이면 Job을 `FAILED`로 전이합니다.
3. 슬롯 획득 후 `CREATED`에서 `RUNNING`으로 조건부 전이합니다.
4. refinement 컨텍스트를 자식 Workspace에 복사합니다.
5. `LLMRetryExecutor`가 `LLMClient`와 parser를 최대 3회 시도합니다.
6. validator가 전체 플랜을 선검증합니다.
7. `ActionExecutor`가 액션을 직렬 실행합니다.
8. 성공 시 `COMPLETED`, 실패 시 `FAILED`로 전이합니다.
9. `finally`에서 semaphore 슬롯을 반환합니다.

### 애플리케이션 시작

1. `OrchestratorConfig`가 endpoint와 자격 증명을 검증합니다.
2. `LifespanResourceProvider`가 shared HTTP client를 생성합니다.
3. `StaleJobRecoveryService`가 15분 이상 stale Job을 원자적으로 실패 처리합니다.
4. FastAPI가 요청 수신을 시작합니다.

## 오류 분류

| 오류 | 재시도 | 최종 처리 |
|---|---|---|
| timeout, 연결 오류 | 예 | 최대 3회 후 `FAILED` |
| HTTP 408, 429, 5xx | 예 | 최대 3회 후 `FAILED` |
| JSON 추출 실패 | 예 | 최대 3회 후 `FAILED` |
| HTTP 3xx | 아니오 | 즉시 `FAILED` |
| HTTP 4xx, 단 408/429 제외 | 아니오 | 즉시 `FAILED` |
| 5MB 응답 초과 | 아니오 | 즉시 `FAILED` |
| schema 또는 보안 검증 실패 | 아니오 | 즉시 `FAILED` |
| 액션 실행 실패 | 아니오 | 즉시 `FAILED`, Workspace 보존 |
| semaphore 10분 timeout | 아니오 | `FAILED` |

## 코드 배치 권고

| 파일 | 역할 |
|---|---|
| `orchestrator/config.py` | 설정 및 endpoint 검증 |
| `orchestrator/service.py` | Job 오케스트레이션 |
| `orchestrator/concurrency.py` | semaphore와 대기 timeout |
| `orchestrator/actions.py` | 액션 dispatch |
| `orchestrator/recovery.py` | stale Job 복구 |
| `llm/client.py` | `LLMClient`, HTTP adapter, bounded reader |
| `llm/retry.py` | HTTP 및 파싱 재시도 정책 |
| `jobs/service.py` | 조건부 상태 전이와 parent Job 생성 확장 |
| `storage/interface.py` | preflight와 디렉터리/복사 연산 확장 |
| `migrations/` | `parent_job_id` idempotent PostgreSQL 변경 SQL |

## 테스트 지점

- config: HTTPS, loopback HTTP, 잘못된 URL, 비밀 누락
- HTTP adapter: shared client, 3xx 거부, 상태 분류, 5MB streaming 중단
- retry executor: 최대 3회, 1초·2초 대기, terminal 오류 즉시 중단
- concurrency gate: 동시 2개, 세 번째 대기, 10분 timeout, 슬롯 반환
- preflight: 404, 409, 파일 누락, 5MB 경계, 자식 Job 미생성
- state repository: 조건부 전이, 동일 트랜잭션 이벤트, 중복 실행 방지
- recovery: 15분 경계, 경쟁 update, 이벤트 중복 방지
- orchestrator: 성공 흐름, refinement 상속, parser/validator 실패, 액션 실패와 Workspace 보존

