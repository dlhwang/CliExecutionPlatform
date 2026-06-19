# 기술 스택 결정 - Unit 5: Iterative Refinement Orchestrator

## 결정 요약

| 영역 | 결정 | 근거 |
|---|---|---|
| HTTP client | `httpx.AsyncClient` | 기존 의존성 재사용, async timeout 및 mock transport 지원 |
| LLM 추상화 | `LLMClient` 인터페이스와 HTTP adapter | 오케스트레이터와 공급자 payload 분리 |
| 백그라운드 실행 | FastAPI `BackgroundTasks` | 현재 단일 프로세스 MVP 구조 유지 |
| 동시성 제한 | 프로세스 로컬 `asyncio.Semaphore(2)` | 사용자 선택과 Unit 3 동시 실행 한도 일치 |
| 재시도 | `asyncio.sleep` 기반 1초, 2초 backoff | 이벤트 루프 비차단 및 결정적 테스트 가능 |
| 상태 저장 | 기존 SQLAlchemy `Job`, `EventLog` | 상태 및 SSE 이벤트 소스 재사용 |
| Job 계보 | `Job.parent_job_id` 자기 참조 FK | 직접 부모 관계를 명시적으로 영속화 |
| 테스트 | fake `LLMClient`, `httpx.MockTransport`, pytest | 실제 외부 호출 없이 계약과 오류 경로 검증 |

## ADR-5-1: httpx AsyncClient 재사용

### 결정

실제 LLM adapter는 `httpx.AsyncClient`를 사용합니다. 애플리케이션 수명 동안 재사용 가능한 client를 의존성으로 제공하고 종료 시 명시적으로 닫습니다.

### 이유

- `requirements.txt`에 이미 포함되어 신규 패키지가 필요하지 않습니다.
- 비동기 FastAPI 백그라운드 흐름에서 이벤트 루프를 차단하지 않습니다.
- 120초 timeout, HTTP 상태 분류, `MockTransport` 테스트를 지원합니다.

## ADR-5-2: 공급자 독립 HTTP 계약

### 결정

오케스트레이터는 `LLMClient.generate_plan(request) -> str` 계약에만 의존합니다. HTTP adapter는 내부 표준 요청을 endpoint별 payload로 변환하고 응답에서 텍스트를 추출합니다.

기본 MVP 표준 계약은 다음 논리 필드를 가집니다.

- 요청: `model`, `prompt`, `context`, `allowed_actions`, `retry_feedback`
- 응답: 액션 플랜을 포함한 텍스트 `content`

특정 공급자의 필드 구조가 다르면 별도 adapter가 동일 인터페이스를 구현합니다.

## ADR-5-3: BackgroundTasks 유지

### 결정

MVP는 외부 Queue 없이 FastAPI `BackgroundTasks`에서 오케스트레이터를 실행합니다.

### 한계

- 프로세스 재시작 시 실행 중 작업은 유실됩니다.
- 이를 보완하기 위해 시작 시 15분 이상 stale 상태인 `RUNNING` Job을 `FAILED`로 전이합니다.
- 지속 실행과 자동 재개가 필요해지면 별도 worker와 durable queue를 후속 도입해야 합니다.

## ADR-5-4: 프로세스 로컬 semaphore

### 결정

오케스트레이터 진입부에서 `asyncio.Semaphore(2)`를 획득합니다. 슬롯 대기 중 Job 상태는 `CREATED`로 유지하고 획득 후 `RUNNING`으로 전이합니다.

### 이유

- LLM 요청과 CLI 실행의 동시 자원 사용을 제한합니다.
- Unit 3의 CLI 실행 한도 2개와 정렬됩니다.
- 분산 카운터 인프라가 필요하지 않습니다.

## ADR-5-5: endpoint 설정 검증

### 결정

URL은 표준 URL parser로 scheme과 host를 검증합니다. 운영은 `https`만 허용하고 개발/테스트의 loopback host만 `http`를 허용합니다.

### 추가 규칙

- endpoint, API key, model은 환경 변수에서 읽습니다.
- URL 내 사용자 정보와 fragment는 허용하지 않습니다.
- 설정값은 사용자 API 입력으로 노출하지 않습니다.
- 오류 로그에는 URL의 민감 query와 인증 정보를 포함하지 않습니다.

## ADR-5-6: Job 자기 참조 스키마

### 결정

`jobs.parent_job_id`를 nullable FK로 추가하고 `jobs.id`를 참조합니다. 부모 삭제 시 자식 Job을 보존할 수 있도록 `ON DELETE SET NULL`을 사용합니다.

### 스키마 적용

- 신규 테스트 DB와 신규 설치는 SQLAlchemy metadata로 생성합니다.
- 이미 생성된 PostgreSQL DB에는 idempotent `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`와 FK 생성 스크립트를 제공합니다.
- MVP에서는 Alembic 의존성을 새로 추가하지 않습니다.

## ADR-5-7: 시작 시 stale Job 정리

### 결정

FastAPI lifespan 시작 과정에서 15분 이상 stale 상태인 `RUNNING` Job을 한 번 조회해 `FAILED`로 전이하고 복구 이벤트를 기록합니다.

### 한계

- 여러 인스턴스가 동시에 시작하면 동일 Job을 처리할 수 있으므로 상태 조건을 포함한 원자적 update 또는 트랜잭션 잠금이 필요합니다.
- MVP 단일 인스턴스에서는 DB 조건부 update로 중복 이벤트를 방지합니다.

## ADR-5-8: 테스트 경계

- 오케스트레이터 단위 테스트는 fake `LLMClient`와 임시 Storage를 사용합니다.
- HTTP adapter 계약 테스트는 `httpx.MockTransport`를 사용합니다.
- timeout과 backoff는 clock/sleep 주입으로 실제 120초를 기다리지 않습니다.
- 외부 LLM endpoint에 대한 실호출은 자동화 테스트에서 수행하지 않습니다.

## 의존성 영향

- 신규 Python 패키지는 추가하지 않습니다.
- 신규 외부 서비스나 배포 리소스는 추가하지 않습니다.
- PostgreSQL 스키마에는 nullable `parent_job_id`와 자기 참조 FK가 추가됩니다.

