# 코드 생성 요약 - Unit 4: SSE Streaming & Event Catch-up

## 구현 결과

Unit 4는 기존 `Job`과 `EventLog`를 읽는 SSE 스트림으로 구현했습니다. 외부 Queue/PubSub과 신규 DB 엔티티 없이 0.5초 DB polling, catch-up, Job별 HMAC 토큰, 전역 20개 연결 제한을 제공합니다.

## 생성 파일

| 파일 | 역할 |
|---|---|
| `sse/__init__.py` | SSE 패키지 공개 라우터 |
| `sse/config.py` | 연결, polling, 배치, 시간 제한 상수 |
| `sse/security.py` | Job별 HMAC-SHA-256 토큰 생성 및 검증 |
| `sse/connection_registry.py` | 프로세스 로컬 20개 연결 슬롯 관리 |
| `sse/repository.py` | 짧은 SQLAlchemy 세션 기반 커서 조회 |
| `sse/encoder.py` | JSON 및 SSE 프레임 인코딩 |
| `sse/service.py` | catch-up, polling, 재시도, 종료 오케스트레이션 |
| `sse/router.py` | 스트림 API와 HTTP 사전 검증 |
| `tests/test_unit_4.py` | Unit 4 자동화 테스트 16개 |

## 수정 파일

| 파일 | 변경 내용 |
|---|---|
| `jobs/schemas.py` | `JobResponse`에 `stream_url`, `stream_token` 추가 |
| `jobs/router.py` | Job 생성 응답에 스트림 접근 정보 생성 |
| `main.py` | SSE 라우터 등록 |
| `tests/conftest.py` | 테스트 비밀키, 세션 팩토리, 연결 레지스트리 격리 |

## 주요 동작

- `GET /api/v1/jobs/{job_id}/stream`
- `X-Stream-Token`으로 Job별 접근 검증
- `Last-Event-ID`가 유효하면 이후 이벤트만 전송
- 비숫자 또는 범위 밖 이벤트 ID는 0으로 정규화
- 이벤트를 ID 오름차순, 최대 100건 단위로 조회
- 동기 DB 조회를 Starlette threadpool에서 실행
- 일시적 DB 오류를 0.5초, 1초, 2초 간격으로 최대 3회 재시도
- 종료 Job은 남은 이벤트 전송 후 `STREAM_END`
- 10분 연결 제한 도달 시 `STREAM_RECONNECT`
- 내부 오류 시 정제된 `STREAM_ERROR`
- 모든 종료 경로에서 연결 슬롯 반환

## 테스트 결과

실행 시각: 2026-06-19T14:08:20+09:00

| 범위 | 결과 |
|---|---|
| Unit 4 | 16 passed |
| 전체 회귀 | 33 passed |
| UTF-8 BOM 검사 | 대상 파일 모두 BOM 없음 |
| `git diff --check` | 통과 |

전체 테스트에는 기존 Unit 3의 미대기 coroutine 관련 경고와 TestClient 폐기 예정 경고가 남아 있으나 테스트 실패는 없습니다.

## 요구사항 검증 증거

| 요구사항/스토리 | 테스트 증거 | 결과 |
|---|---|---|
| S-1 | `test_job_creation_returns_stream_access` | PASS |
| S-2 | `test_sse_streaming_completed_job` | PASS |
| S-3 | `test_sse_catchup_after_last_event_id` | PASS |
| BR-4-1, NFR-4-7 | `test_stream_rejects_missing_job_and_invalid_token` | PASS |
| BR-4-3 | `test_last_event_id_invalid_or_out_of_range_restarts_from_first` | PASS |
| BR-4-4, BR-4-5 | `test_sse_streaming_completed_job` | PASS |
| BR-4-7, BR-4-8 | `test_sse_streaming_completed_job`, `test_running_job_terminal_drain` | PASS |
| NFR-4-1 | `test_connection_registry_rejects_twenty_first_connection`, `test_stream_endpoint_returns_503_at_connection_capacity` | PASS |
| NFR-4-2 | `test_twenty_streams_average_delivery_under_three_seconds` | PASS |
| NFR-4-3 | `test_repository_uses_cursor_order_and_batch_limit` | PASS |
| NFR-4-4 | `test_stream_emits_reconnect_at_max_duration` | PASS |
| NFR-4-6 | `test_transient_db_error_retries_three_times`, `test_connection_slot_released_on_error` | PASS |
| NFR-4-7, NFR-4-8 | `test_stream_token_is_job_scoped`, `test_missing_secret_is_rejected` | PASS |

## N/A 항목

- DB 마이그레이션: 기존 `Job`, `EventLog`만 사용하고 토큰은 상태 비저장 HMAC 방식이므로 필요하지 않습니다.
- 외부 인프라: Redis, Kafka, RabbitMQ를 도입하지 않았습니다.
- 네이티브 브라우저 `EventSource`: `X-Stream-Token` 사용자 지정 헤더를 지원하지 않으므로 fetch streaming 또는 polyfill이 필요합니다.
- 실제 PostgreSQL 성능 시험: 자동화 테스트는 SQLite 파일 DB에서 20개 동시 논리 스트림의 평균 지연을 검증했습니다. 운영 PostgreSQL 부하 시험은 최종 Build and Test의 성능 검증 대상으로 남깁니다.

## 확장 규칙 준수

- Security Baseline: 비활성화되어 N/A
- Property-Based Testing: 비활성화되어 N/A

