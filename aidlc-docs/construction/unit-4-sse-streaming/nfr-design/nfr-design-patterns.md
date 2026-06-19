# 비기능 설계 패턴 - Unit 4: SSE Streaming & Event Catch-up

## 설계 목표

승인된 SSE 요구사항을 단일 FastAPI 인스턴스에서 구현하되, async 이벤트 루프 차단과 DB 커넥션 장기 점유를 방지합니다. 외부 Queue/PubSub 없이 20개 연결과 평균 3초 이내 전달을 목표로 합니다.

## ND-4-1: 제한된 DB 재시도

- 재시도 대상은 일시적인 SQLAlchemy `OperationalError` 및 연결 무효화가 확인된 `DBAPIError`로 제한합니다.
- 최초 실패 후 0.5초, 1초, 2초 간격으로 최대 3회 재시도합니다.
- 각 재시도는 새 `SessionLocal` 세션에서 실행하며 실패한 세션은 즉시 rollback 및 close합니다.
- 영구 오류, 데이터 오류, 프로그래밍 오류는 재시도하지 않습니다.
- 재시도가 모두 실패하면 토큰이나 DB 접속 정보를 포함하지 않은 `STREAM_ERROR` 프레임을 가능한 경우 전송하고 연결을 종료합니다.
- 클라이언트 연결 취소는 재시도하지 않고 즉시 전파합니다.

## ND-4-2: 100건 제한 커서 조회

- 조회 조건은 `job_id == 요청 Job`, `id > last_seen_id`, `id ASC`, `LIMIT 100`입니다.
- 조회 결과가 100건이면 대기 없이 다음 배치를 조회해 catch-up을 계속합니다.
- 조회 결과가 100건 미만이고 Job이 진행 중이면 0.5초 대기 후 다시 조회합니다.
- 마지막으로 성공적으로 SSE 프레임을 생성한 이벤트 ID만 연결 로컬 커서에 반영합니다.
- Job이 종료 상태여도 미전송 이벤트 배치를 모두 비운 후 `STREAM_END`를 전송합니다.

## ND-4-3: 짧은 세션과 threadpool 격리

- async generator에서 동기 SQLAlchemy 함수를 직접 호출하지 않습니다.
- 각 polling 조회는 FastAPI/Starlette threadpool에서 실행합니다.
- threadpool에 전달되는 동기 함수 내부에서 세션을 생성하고 조회가 끝나면 닫습니다.
- ORM 세션이나 ORM 객체를 서로 다른 thread 사이에서 공유하지 않습니다.
- threadpool 함수는 SSE에 필요한 원시 값 또는 불변 DTO를 반환합니다.
- 스트림 수명 동안 DB 세션을 보관하지 않습니다.

## ND-4-4: 전역 연결 벌크헤드

- 프로세스 단위 전역 활성 연결 상한은 20개입니다.
- Job별 연결 제한은 적용하지 않습니다.
- 라우터는 `StreamingResponse`를 반환하기 전에 연결 슬롯을 원자적으로 예약해야 합니다.
- 슬롯이 없으면 스트림을 시작하지 않고 HTTP 503을 반환합니다.
- 스트림 정상 종료, 오류, 타임아웃, 클라이언트 취소 모두 `finally`에서 슬롯을 정확히 한 번 반환합니다.
- 다중 worker에서는 worker별 20개로 동작하며 전역 분산 제한은 MVP 범위에서 제외합니다.

## ND-4-5: 상태 비저장 HMAC 인증

- 토큰은 HMAC-SHA-256과 `SSE_STREAM_TOKEN_SECRET`으로 정규화된 Job UUID를 서명해 생성합니다.
- 응답 토큰은 버전과 URL-safe Base64 서명을 포함하는 형식으로 고정합니다.
- 요청은 `X-Stream-Token` 헤더로 토큰을 전달합니다.
- 서버는 요청 경로의 Job ID로 기대 서명을 다시 계산하고 `hmac.compare_digest`로 비교합니다.
- 누락, 형식 오류, 서명 불일치에는 동일한 HTTP 403 응답을 사용해 검증 상세를 노출하지 않습니다.
- 비밀키와 토큰은 로그 필드, 예외 메시지, SSE 데이터에 포함하지 않습니다.

## ND-4-6: 연결 수명과 재연결

- 스트림 시작 시 monotonic clock으로 종료 시각을 계산합니다.
- 최대 10분에 도달하면 `STREAM_RECONNECT` 제어 프레임을 보내고 연결을 닫습니다.
- 저장 이벤트 프레임에는 항상 SSE `id`를 포함합니다.
- 재연결 시 유효한 `Last-Event-ID` 이후부터 조회합니다.
- 전달 보장은 at-least-once이며 클라이언트는 이벤트 ID로 중복 제거합니다.

## ND-4-7: SSE 프레임 안전성

- `data`는 JSON 직렬화 후 단일 SSE 프레임으로 인코딩합니다.
- 메시지의 개행과 특수문자는 JSON 인코더에 맡기며 문자열 결합으로 JSON을 만들지 않습니다.
- EventLog 기반 프레임은 `id`, `event`, `data`를 포함합니다.
- 제어 프레임은 DB 이벤트 ID를 사용하지 않아 클라이언트의 저장 이벤트 커서를 변경하지 않습니다.
- 응답 헤더는 최소 `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `Connection: keep-alive`를 포함합니다.

## 클라이언트 호환성 제약

브라우저 기본 `EventSource` API는 임의 요청 헤더를 설정할 수 없습니다. `X-Stream-Token` 계약을 사용하는 웹 클라이언트는 fetch streaming 또는 사용자 지정 헤더를 지원하는 SSE polyfill을 사용해야 합니다. SSE wire format 자체는 표준을 유지합니다.

## 검증 매핑

| 요구사항 | 설계 패턴 | 핵심 검증 |
|---|---|---|
| NFR-4-1 | ND-4-4 | 20개 허용, 21번째 HTTP 503, 슬롯 반환 |
| NFR-4-2 | ND-4-2, ND-4-3 | 20개 연결에서 평균 3초 이내 |
| NFR-4-3 | ND-4-2, ND-4-3 | 인덱스 조건, LIMIT 100, 세션 즉시 close |
| NFR-4-4 | ND-4-6 | 10분 종료와 `Last-Event-ID` 재연결 |
| NFR-4-5 | ND-4-2, ND-4-6 | ID 오름차순과 중복 허용 |
| NFR-4-6 | ND-4-1, ND-4-4 | 오류, 취소, 정상 종료 정리 |
| NFR-4-7 | ND-4-5 | 유효, 무효, 타 Job 토큰 |
| NFR-4-8 | ND-4-5 | 비밀키 누락 및 로그 비노출 |

