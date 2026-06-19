# 코드 생성 계획서 - Unit 4: SSE Streaming & Event Catch-up

> 이 문서는 Unit 4 Code Generation의 단일 정보 출처입니다. 승인 후 아래 생성 단계를 순서대로 실행하고 완료 즉시 체크박스를 갱신합니다.

## 유닛 컨텍스트

| 항목 | 내용 |
|---|---|
| 프로젝트 유형 | Greenfield / Monolith |
| 애플리케이션 코드 | `D:\workspace\CLI-Execution-Platform\sse\` 및 기존 `jobs/`, `main.py` |
| 테스트 | `D:\workspace\CLI-Execution-Platform\tests\test_unit_4.py` |
| 코드 문서 | `aidlc-docs/construction/unit-4-sse-streaming/code/code-summary.md` |
| 선행 유닛 | Unit 1 `Job`, `EventLog`, DB와 API 기반; Unit 3 EventLog 생산 |
| 소유 데이터 | 신규 영속 엔티티 없음. 기존 `Job`, `EventLog` 읽기 전용 사용 |

## 스토리 추적성

| 스토리 | 구현 범위 | 검증 |
|---|---|---|
| S-1 | Job 생성 응답에 `stream_url`, `stream_token` 포함 | `test_job_creation_returns_stream_access` |
| S-2 | 저장 EventLog를 SSE 프레임으로 순차 전송 | `test_sse_streaming_completed_job` |
| S-3 | `Last-Event-ID` 이후 이벤트 catch-up | `test_sse_catchup_after_last_event_id` |

## 요구사항 검증 매핑

| 요구사항 | 검증 테스트 |
|---|---|
| BR-4-1, NFR-4-7 | `test_stream_rejects_missing_job_and_invalid_token` |
| BR-4-3 | `test_last_event_id_invalid_or_out_of_range_restarts_from_first` |
| BR-4-4, BR-4-5 | `test_sse_streaming_completed_job` |
| BR-4-7, BR-4-8 | `test_sse_streaming_completed_job`, `test_running_job_terminal_drain` |
| NFR-4-1 | `test_connection_registry_rejects_twenty_first_connection` |
| NFR-4-2 | `test_twenty_streams_average_delivery_under_three_seconds` |
| NFR-4-3 | `test_repository_uses_cursor_order_and_batch_limit` |
| NFR-4-4 | `test_stream_emits_reconnect_at_max_duration` |
| NFR-4-6 | `test_transient_db_error_retries_three_times`, `test_connection_slot_released_on_error` |
| NFR-4-7, NFR-4-8 | `test_stream_token_is_job_scoped`, `test_missing_secret_is_rejected` |

## Part 1: 계획 수립 체크리스트

- [x] P1: 기능 설계, NFR Requirements, NFR Design 분석
- [x] P2: 기존 FastAPI, Job API, DB 세션, 테스트 fixture 분석
- [x] P3: 변경 및 생성 파일 경로 확정
- [x] P4: 스토리와 요구사항별 자동화 테스트 매핑
- [x] P5: 코드 생성 계획 작성 및 승인 요청 기록
- [x] P6: 사용자 계획 승인 기록

## Part 2: 생성 단계 체크리스트

### Step 1: 설정과 Job별 토큰 구현

- [x] `sse/config.py` 생성: 연결 20개, polling 0.5초, 배치 100건, 최대 600초, 재시도 지연 정의
- [x] `sse/security.py` 생성: HMAC-SHA-256 토큰 생성/검증, `SSE_STREAM_TOKEN_SECRET` 검증
- [x] 토큰 또는 비밀키가 로그와 오류 응답에 노출되지 않도록 구현

### Step 2: 연결 제한과 DB 조회 구현

- [x] `sse/connection_registry.py` 생성: 원자적 전역 슬롯 예약/반환, 최대 20개
- [x] `sse/repository.py` 생성: 세션 팩토리 기반 짧은 세션, Job 상태 및 커서 조회, `LIMIT 100`
- [x] ORM 객체 대신 스트림용 불변 DTO 반환

### Step 3: SSE 인코더와 스트림 서비스 구현

- [x] `sse/encoder.py` 생성: UTF-8 JSON 기반 EventLog 및 제어 프레임 인코딩
- [x] `sse/service.py` 생성: threadpool DB 호출, catch-up, polling, terminal drain
- [x] DB 일시 오류에 0.5초, 1초, 2초 최대 3회 재시도
- [x] 10분 도달 시 `STREAM_RECONNECT`, Job 종료 시 `STREAM_END`, 오류 시 `STREAM_ERROR`
- [x] 모든 종료 경로에서 연결 슬롯 반환

### Step 4: API 통합

- [x] `sse/router.py`, `sse/__init__.py` 생성
- [x] 스트림 시작 전 HTTP 404, 403, 503 검증
- [x] `X-Stream-Token`, `Last-Event-ID` 헤더 처리
- [x] `jobs/schemas.py` 수정: Job 생성 응답에 `stream_url`, `stream_token` 추가
- [x] `jobs/router.py` 수정: Job별 토큰과 스트림 URL 생성
- [x] `main.py` 수정: SSE 라우터 등록
- [x] 세션 팩토리와 연결 레지스트리를 의존성으로 분리해 테스트 대체 가능하게 구성

### Step 5: Unit 4 자동화 테스트 구현

- [x] `tests/conftest.py` 수정: 테스트 비밀키와 SSE 세션 팩토리/레지스트리 격리
- [x] `tests/test_unit_4.py` 생성: S-1, S-2, S-3 및 BR/NFR 검증
- [x] 토큰, HTTP 오류, 순서, catch-up, 잘못된 커서, 종료 제어 이벤트 검증
- [x] 재시도, 100건 배치, 20개 제한, 슬롯 반환, 10분 제한 검증
- [x] 20개 논리 스트림의 평균 전달 지연 3초 이내 검증

### Step 6: 테스트 및 회귀 검증

- [x] Unit 4 테스트 실행 (15 passed)
- [x] 전체 pytest 실행으로 Unit 1-3 회귀 없음 확인 (33 passed)
- [x] 실패 시 원인 수정 후 동일 범위 재실행 (pytest 임시 경로 권한 문제를 작업공간 `--basetemp`로 해결)
- [x] 모든 변경/생성 파일이 UTF-8 BOM 없음인지 검증

### Step 7: 코드 요약과 추적성 증거 작성

- [x] `aidlc-docs/construction/unit-4-sse-streaming/code/code-summary.md` 생성
- [x] 생성/수정 파일, 설계 결정, 테스트 결과 기록
- [x] 스토리 및 요구사항별 테스트 증거 기록
- [x] 자동화하지 못한 검증이 있으면 N/A 사유 기록

### Step 8: 완료 상태 갱신

- [x] 모든 생성 단계 체크박스 완료 확인
- [x] `aidlc-state.md`를 Unit 4 Code Generation 승인 대기로 갱신
- [x] 표준 Code Generation 완료 메시지 제시

## 변경 파일 목록

### 신규 애플리케이션 파일

- `sse/__init__.py`
- `sse/config.py`
- `sse/security.py`
- `sse/connection_registry.py`
- `sse/repository.py`
- `sse/encoder.py`
- `sse/service.py`
- `sse/router.py`
- `tests/test_unit_4.py`

### 수정 파일

- `jobs/schemas.py`
- `jobs/router.py`
- `main.py`
- `tests/conftest.py`

### 문서 파일

- `aidlc-docs/construction/unit-4-sse-streaming/code/code-summary.md`

## 제외 항목

- DB 스키마 및 마이그레이션: 상태 비저장 HMAC 토큰과 기존 엔티티를 사용하므로 N/A
- 신규 배포/인프라 산출물: 외부 Queue/PubSub을 도입하지 않으므로 N/A
- 네이티브 브라우저 `EventSource`: 사용자 지정 헤더 미지원으로 fetch streaming 또는 polyfill 필요

## 승인 상태

- **상태**: 생성 완료, 코드 검토 승인 대기
- **승인 후 동작**: Step 1부터 Step 8까지 순차 구현
