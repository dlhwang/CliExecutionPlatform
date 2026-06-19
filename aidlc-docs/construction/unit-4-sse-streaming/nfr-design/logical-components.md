# 논리 컴포넌트 - Unit 4: SSE Streaming & Event Catch-up

## 컴포넌트 구성

### SSEStreamRouter

책임:

- `GET /api/v1/jobs/{job_id}/stream` 요청 처리
- `X-Stream-Token`과 `Last-Event-ID` 헤더 수집
- Job 존재 및 토큰 검증
- 연결 슬롯 사전 예약과 HTTP 404, 403, 503 응답 결정
- `StreamingResponse` 생성

라우터는 스트림 응답을 시작하기 전에 모든 HTTP 오류를 확정해야 합니다.

### StreamTokenService

책임:

- Job 생성 응답에 포함할 Job별 HMAC 토큰 생성
- 토큰 버전 및 Base64 형식 검증
- 요청 Job ID에 대한 기대 서명 계산
- 상수 시간 서명 비교

의존성:

- 환경 변수 `SSE_STREAM_TOKEN_SECRET`
- 표준 라이브러리 `hmac`, `hashlib`, `base64`

### ConnectionRegistry

책임:

- 프로세스 내 활성 SSE 연결 수 관리
- 최대 20개 슬롯의 원자적 예약과 반환
- 중복 반환 방지
- 현재 연결 수 관측값 제공

Job별 카운터는 관리하지 않습니다. 구현은 `asyncio.Lock`으로 보호되는 카운터 또는 동등한 비동기 동기화 수단을 사용합니다.

### EventLogPollingRepository

책임:

- threadpool에서 실행되는 동기 DB 조회 제공
- 요청마다 `SessionLocal` 생성 및 종료
- Job 존재/상태 조회
- `id > last_seen_id`, 오름차순, 최대 100건 이벤트 조회
- ORM 객체를 스트림 thread로 전달하지 않고 DTO로 변환

권장 반환 DTO 필드:

- `event_id`
- `job_id`
- `event_type`
- `message`
- `created_at`
- `job_status`

### PollingRetryExecutor

책임:

- 일시적 DB 예외 분류
- 0.5초, 1초, 2초 재시도 스케줄 적용
- 취소 신호 즉시 전파
- 재시도 소진 시 정제된 스트림 오류 생성

재시도 대기는 async sleep을 사용해 이벤트 루프와 worker thread를 점유하지 않습니다.

### SSEStreamService

책임:

- 연결 로컬 `last_seen_id`와 monotonic 종료 시각 관리
- polling repository를 threadpool로 호출
- 100건 배치 catch-up과 0.5초 polling 제어
- 종료 상태에서 남은 이벤트 drain
- 10분 도달 시 `STREAM_RECONNECT` 생성
- Job 종료 시 `STREAM_END` 생성
- 오류 시 `STREAM_ERROR` 생성
- 모든 종료 경로에서 연결 슬롯 반환 보장

### SSEFrameEncoder

책임:

- EventLog DTO를 UTF-8 SSE 프레임으로 인코딩
- JSON 직렬화
- 저장 이벤트와 제어 이벤트 형식 분리
- 토큰 및 내부 예외 정보가 payload에 포함되지 않도록 제한

## 처리 순서

1. `SSEStreamRouter`가 Job 존재 여부를 확인합니다.
2. `StreamTokenService`가 `X-Stream-Token`을 검증합니다.
3. `ConnectionRegistry`가 슬롯을 예약합니다. 실패하면 HTTP 503을 반환합니다.
4. 라우터가 `SSEStreamService`의 async generator로 `StreamingResponse`를 생성합니다.
5. 서비스는 `EventLogPollingRepository`를 threadpool에서 호출합니다.
6. `PollingRetryExecutor`가 일시적 DB 오류만 최대 3회 재시도합니다.
7. `SSEFrameEncoder`가 최대 100개 이벤트를 ID 순서로 인코딩합니다.
8. 이벤트가 더 남았으면 즉시 다음 배치를 조회하고, 없으면 0.5초 대기합니다.
9. Job 종료, 10분 제한, 내부 오류, 클라이언트 취소 중 하나가 발생하면 규칙에 맞게 종료합니다.
10. `finally` 블록이 연결 슬롯을 반환합니다.

## 상태 및 경계 조건

| 조건 | 동작 |
|---|---|
| Job 없음 | 스트림 시작 전 HTTP 404 |
| 토큰 누락/불일치 | 스트림 시작 전 HTTP 403 |
| 활성 연결 20개 | 21번째 요청 HTTP 503 |
| 잘못된 `Last-Event-ID` | 0으로 정규화해 첫 이벤트부터 전송 |
| 100건 조회 | 대기 없이 다음 배치 조회 |
| 진행 중이며 새 이벤트 없음 | 0.5초 async sleep |
| 종료 Job이며 미전송 이벤트 있음 | 모두 drain 후 `STREAM_END` |
| DB 일시 오류 | 최대 3회 재시도 후 `STREAM_ERROR` |
| 연결 10분 도달 | `STREAM_RECONNECT` 후 종료 |
| 클라이언트 연결 해제 | 취소 처리 후 슬롯 반환 |

## 코드 배치 권고

| 파일 | 역할 |
|---|---|
| `sse/router.py` | 엔드포인트와 HTTP 사전 검증 |
| `sse/service.py` | async 스트림 오케스트레이션 |
| `sse/repository.py` | 짧은 동기 DB 조회 |
| `sse/security.py` | HMAC 토큰 생성 및 검증 |
| `sse/connection_registry.py` | 전역 연결 슬롯 관리 |
| `sse/encoder.py` | SSE 프레임 직렬화 |
| `sse/config.py` | 연결 수, polling, 배치, 시간 제한 설정 |

실제 파일 분리는 Code Generation 계획에서 기존 코드 규모와 테스트 편의성을 기준으로 조정할 수 있습니다.

## 테스트 지점

- repository: 조회 조건, 정렬, 100건 제한, 세션 종료
- token service: Job별 토큰 격리, 형식 오류, 상수 시간 비교 경로
- registry: 동시 예약 경쟁, 21번째 거절, 중복 반환 방지
- retry executor: 재시도 간격, 비재시도 오류, 취소 전파
- stream service: catch-up, polling, terminal drain, 10분 제한, 오류 종료
- router: HTTP 404/403/503이 스트림 시작 전에 반환되는지 검증
- encoder: 개행 및 특수문자 JSON 직렬화, UTF-8 프레임 형식

