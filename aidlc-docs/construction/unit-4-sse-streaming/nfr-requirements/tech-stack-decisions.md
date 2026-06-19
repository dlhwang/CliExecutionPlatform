# 기술 스택 결정 - Unit 4: SSE Streaming & Event Catch-up

## 결정 요약

| 영역 | 결정 | 근거 |
|---|---|---|
| SSE 응답 | FastAPI `StreamingResponse`와 async generator | 기존 FastAPI 스택을 재사용하고 추가 의존성을 피함 |
| 이벤트 공급 | 0.5초 DB polling | 현재 `EventLog` 저장 구조에서 별도 인프라 없이 구현 가능 |
| DB 접근 | 기존 SQLAlchemy 및 PostgreSQL | 기존 모델, 인덱스, 커넥션 풀을 재사용 |
| 접근 제어 | Job ID에 대한 HMAC 서명 토큰 | Job별 토큰을 제공하면서 신규 저장 컬럼과 외부 인증 인프라를 피함 |
| 연결 제한 | 프로세스 로컬 비동기 semaphore/counter | 단일 인스턴스 MVP의 20개 상한에 적합 |
| 직렬화 | 표준 JSON 및 SSE 텍스트 프레임 | 브라우저 EventSource 호환성과 기존 이벤트 모델 유지 |

## ADR-4-1: DB polling 유지

### 결정

MVP에서는 Queue/PubSub을 도입하지 않고 0.5초 간격으로 `event_logs`를 polling합니다.

### 이유

- 현재 이벤트 생산자는 DB에 직접 `EventLog`를 기록합니다.
- Queue/PubSub 도입 시 이벤트 생산 경로, 장애 복구, 배포 구성, 테스트 범위가 함께 변경됩니다.
- 목표 동시 연결 수가 20개이고 허용 평균 지연이 3초이므로 인덱스 기반 polling으로 검증 가능한 범위입니다.

### 제약

- 각 polling 작업은 짧은 DB 세션을 사용하고 즉시 반환해야 합니다.
- 연결당 최대 초당 2회 조회가 발생하므로 20개 연결에서 기본 이벤트 조회 부하는 초당 약 40회입니다.
- 성능 기준을 충족하지 못하면 polling 간격 조정이 아니라 Job별 fan-out 또는 Pub/Sub 전환을 후속 설계로 검토합니다.

## ADR-4-2: FastAPI StreamingResponse 사용

### 결정

추가 SSE 패키지 없이 FastAPI/Starlette의 `StreamingResponse`와 async generator로 `text/event-stream` 응답을 생성합니다.

### 이유

- 현재 의존성으로 구현할 수 있습니다.
- 프레임 규격과 종료 조건이 단순하여 별도 라이브러리의 이점이 제한적입니다.
- 클라이언트 연결 해제 시 generator 취소 처리를 직접 테스트할 수 있습니다.

## ADR-4-3: 상태 비저장 Job별 HMAC 토큰

### 결정

서버는 `SSE_STREAM_TOKEN_SECRET`을 사용해 Job ID를 HMAC-SHA-256으로 서명한 토큰을 Job 생성 시 반환합니다. 스트림 요청은 전용 헤더로 토큰을 제출합니다.

### 이유

- 공유 API Key보다 Job 간 권한 범위를 분리합니다.
- 표준 라이브러리 `hmac`, `hashlib`, `base64`로 구현할 수 있습니다.
- 서명 검증만 수행하므로 토큰 저장 컬럼과 DB 마이그레이션이 필요하지 않습니다.

### 보안 제약

- 토큰은 해당 Job이 존재하는 동안만 유효한 Job 범위 자격 증명으로 취급합니다.
- 비밀키 교체 시 기존 토큰은 무효화됩니다.
- 비교에는 `hmac.compare_digest`를 사용합니다.
- TLS 종단은 배포 환경 책임이며 평문 네트워크에서 토큰을 전송하면 안 됩니다.

## ADR-4-4: 10분 연결 후 재연결

### 결정

각 SSE 연결은 최대 10분 유지한 뒤 재연결을 유도합니다.

### 이유

- 장기 연결에 따른 리소스 누수를 제한합니다.
- `Last-Event-ID` catch-up 기능으로 재연결 중 누락 이벤트를 복구할 수 있습니다.
- 토큰은 Job 범위에서 유지되므로 같은 토큰으로 재연결할 수 있습니다.

## ADR-4-5: 프로세스 로컬 연결 제한

### 결정

단일 인스턴스 MVP는 프로세스 로컬 semaphore 또는 원자적 카운터로 최대 20개 연결을 제한합니다.

### 한계

- 여러 worker 또는 인스턴스를 실행하면 제한은 프로세스별로 적용됩니다.
- 전역 제한이 필요해지는 시점에는 Redis 등 공유 저장소 기반 lease/counter를 별도 설계해야 합니다.

## 의존성 영향

- `requirements.txt`에 신규 런타임 패키지를 추가하지 않습니다.
- 외부 메시지 브로커나 캐시 인프라를 추가하지 않습니다.
- 기존 PostgreSQL의 `idx_event_logs_job_id_id` 인덱스를 사용합니다.

