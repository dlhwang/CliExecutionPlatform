# 단위 테스트 실행 지침서 (Unit Test Execution Instructions)

## 개요

본 프로젝트의 모든 테스트는 **pytest** 기반 통합 테스트로 구성되며,
SQLite 인메모리 DB를 활용하여 PostgreSQL 없이 완전 자동화 실행이 가능합니다.

---

## 테스트 환경 요구 사항

- Python 3.10+ 가상 환경 활성화 상태
- `pip install -r requirements.txt` 완료
- 실제 OpenSCAD CLI **불필요** (Unit 3 테스트는 Python 인터프리터 및 Mock으로 대체)

---

## 전체 테스트 실행

### 1. 전체 유닛 테스트 일괄 실행

```bash
pytest tests/ -v
```

### 2. 유닛별 개별 실행

```bash
# Unit 1: API Core & Storage Service
pytest tests/test_unit_1.py -v

# Unit 2: Parser & Policy Validator Service
pytest tests/test_unit_2.py -v

# Unit 3: CLI Runner Service
pytest tests/test_unit_3.py -v
```

### 3. 특정 테스트 케이스 단독 실행

```bash
pytest tests/test_unit_3.py::test_timeout_kills_process -v
```

---

## 테스트 결과 요약 (Build and Test 단계 실측 기준)

| 유닛 | 테스트 파일 | 테스트 수 | 통과 | 실패 | 상태 |
|------|-----------|---------|------|------|------|
| Unit 1 | `test_unit_1.py` | 4 | 4 | 0 | ✅ PASS |
| Unit 2 | `test_unit_2.py` | 5 | 5 | 0 | ✅ PASS |
| Unit 3 | `test_unit_3.py` | 8 | 8 | 0 | ✅ PASS |
| Unit 4 | `test_unit_4.py` | 16 | 16 | 0 | ✅ PASS |
| Unit 5 | `test_unit_5.py` | 12 | 12 | 0 | ✅ PASS |
| **합계** | | **45** | **45** | **0** | ✅ **ALL PASS** |

**실행 시간**: 3.25초 (로컬 SQLite 인메모리, 평균)

---

## 테스트 케이스 매핑 (기능 요구사항 검증 증거)

### Unit 1 테스트

| 테스트 함수 | 검증 스토리/요구사항 | 내용 |
|-----------|------------------|------|
| `test_job_creation` | S-1 | UUIDv7 발급, DB CREATED 저장, Workspace 디렉토리 생성 검증 |
| `test_directory_traversal_protection` | S-4 | `../` 경로 탈출 시 HTTP 403 반환 및 `PermissionError` 발생 검증 |
| `test_rate_limiting` | NFR Rate Limiting | 분당 10회 초과 시 HTTP 429 반환 검증 |
| `test_artifact_download` | S-4 | 정상 아티팩트 다운로드 바이트 검증 + FAILED Job 접근 거부 검증 |

### Unit 2 테스트

| 테스트 함수 | 검증 스토리/요구사항 | 내용 |
|-----------|------------------|------|
| `test_json_extraction_success` | S-6 | Markdown 코드블록 + Fallback `[…]` JSON 추출 성공 검증 |
| `test_parser_retryable_exception` | S-6 | JSON 구문 오류 시 `LLMPlanRetryableException` 발생 검증 |
| `test_parser_validation_exception` | S-6 | 잘못된 action 타입/누락 필드 시 `LLMPlanValidationError` 발생 검증 |
| `test_security_validator_path_protection` | S-6 | 경로 침투/절대경로/Symlink 차단 + DB SECURITY_ALERT 로그 검증 |
| `test_security_validator_tool_whitelist` | S-6 | 비인가 Tool(bash 등) 차단 및 openscad 통과 검증 |

### Unit 3 테스트

| 테스트 함수 | 검증 NFR/스토리 | 내용 |
|-----------|--------------|------|
| `test_argument_validation_blocks_unsafe_chars` | NFR-1.4 | 세미콜론/파이프/달러/공백 등 위험 인자 Allowlist 차단 검증 |
| `test_argument_validation_allows_safe_args` | NFR-1.4 | OpenSCAD 정상 인자 통과 검증 |
| `test_run_tool_success_writes_event_logs` | US-3-1, Q2 | 정상 실행 + EventLog CLI_OUTPUT DB 적재 검증 |
| `test_timeout_kills_process` | NFR-1.1 | 30초 타임아웃 시 process.kill() + CLIExecutionTimeoutError 검증 |
| `test_timeout_preserves_partial_logs` | Q4 | 타임아웃 후 부분 출력 보존 + TIMEOUT 마커 기록 검증 |
| `test_launch_retry_on_os_error` | NFR-1.3 | OSError 시 최대 2회 재시도 → CLIExecutionLaunchError 검증 |
| `test_nonzero_exit_code_raises_cli_execution_error` | US-3-1 | Non-Zero Exit Code 시 CLIExecutionError 발생 검증 |
| `test_semaphore_limits_concurrency` | NFR-1.2 | Semaphore(2) 동시성 제한 검증 |

### Unit 4 테스트

| 테스트 함수 | 검증 NFR/스토리 | 내용 |
|-----------|--------------|------|
| `test_job_creation_returns_stream_access` | S-1 | Job 생성 응답의 스트림 접근 정보(url 및 token) 발급 검증 |
| `test_sse_streaming_completed_job` | US-3-1 | 완료 Job에 대한 실시간 스트림 결과값 및 STREAM_END 전송 검증 |
| `test_sse_catchup_after_last_event_id` | Q3 | Last-Event-ID 지정 시 누락 이벤트부터 복원(catch-up)하여 전송 검증 |
| `test_last_event_id_invalid_or_out_of_range_restarts_from_first` | Q3 | Last-Event-ID가 유효하지 않거나 범위 밖인 경우 첫 이벤트부터 재전송 검증 |
| `test_stream_rejects_missing_job_and_invalid_token` | NFR-4.1 | 잘못된 token 혹은 존재하지 않는 job 접근 시 HTTP 403 / 404 차단 검증 |
| `test_stream_token_is_job_scoped` | NFR-4.1 | 스트림 토큰이 Job-scoped으로 서로 다른 Job에 사용될 수 없는지 검증 |
| `test_missing_secret_is_rejected` | NFR-4.1 | SSE_STREAM_TOKEN_SECRET 환경변수가 없을 경우 설정 오류 검증 |
| `test_connection_registry_rejects_twenty_first_connection` | NFR-4.3 | 동시 21번째 연결에 대해 acquire 거부 (동시 20개 접속 제한) |
| `test_stream_endpoint_returns_503_at_connection_capacity` | NFR-4.3 | 연결 한계(20개) 도달 시 HTTP 503 반환 및 STREAM_CAPACITY_EXCEEDED 검증 |
| `test_repository_uses_cursor_order_and_batch_limit` | NFR-4.2 | 이벤트 조회 시 ID 순서 정렬 및 batch 크기 제한(100개) 검증 |
| `test_stream_emits_reconnect_at_max_duration` | NFR-4.4 | 10분(600초) 이상 세션 유지 시 자동 재연결(STREAM_RECONNECT) 및 연결 해제 검증 |
| `test_transient_db_error_retries_three_times` | NFR-4.5 | DB 일시적 장애 시 지수 백오프(0.5, 1, 2) 적용하여 최대 3회 재시도 검증 |
| `test_connection_slot_released_on_error` | NFR-4.6 | 비즈니스 로직 오류 발생 시 스트림 세션 반환 및 STREAM_ERROR 전송 검증 |
| `test_running_job_terminal_drain` | US-3-1 | 실행 중인 Job이 완료될 때까지 지속 폴링하며 데이터를 보내고 완료 시 STREAM_END 전송 검증 |
| `test_twenty_streams_average_delivery_under_three_seconds` | NFR-4.7 | 20개 동시 스트림 처리 시 평균 전달 지연 시간이 3초 미만임을 검증 |

### Unit 5 테스트

| 테스트 함수 | 검증 NFR/스토리 | 내용 |
|-----------|--------------|------|
| `test_refinement_creates_child_job` | S-5 | 이전 완료 Job 기반 refinement 시 parent_job_id 설정된 CREATED 자식 Job 생성 검증 |
| `test_refinement_rejects_invalid_parent_or_missing_files` | BR-5-3, BR-5-5 | 부모가 없거나 RUNNING 상태이거나, 혹은 model.scad/design-spec.md가 없는 경우 refinement HTTP 404/409 오류 검증 |
| `test_refinement_rejects_context_over_five_mb` | BR-5-4 | 부모의 model.scad/design-spec.md 크기 합이 5MB 초과 시 refinement HTTP 413 오류 검증 |
| `test_refinement_copies_context_and_calls_llm` | S-5 | 자식 Job 실행 시 부모 workspace의 model.scad 및 design-spec.md 상속 및 LLM 컨텍스트 전송, 파싱된 write_file 액션 수행 검증 |
| `test_job_state_transitions_and_duplicate_execution` | BR-5-7, BR-5-16 | CREATED -> RUNNING -> COMPLETED 전체 상태 전이 및 동일 Job의 중복 실행 시 차단 검증 |
| `test_llm_retry_classification_and_backoff` | BR-5-9, NFR-5-5 | LLM Client 임시 장애 시 지수 백오프(1초, 2초) 및 최대 2회 재시도 검증 |
| `test_concurrency_gate_limits_two_jobs_and_times_out_waiter` | NFR-5-2 | 동시 오케스트레이션 실행 2개 제한 및 3번째 요청 시 대기 타임아웃 검증 |
| `test_endpoint_security_and_secret_validation` | NFR-5-9, NFR-5-10 | 프로덕션 환경의 LLM Endpoint가 HTTPS가 아니거나 Secret이 없을 때 설정 오류 검증 |
| `test_redirect_and_response_size_are_rejected` | NFR-5-11, NFR-5-4 | LLM 응답 수신 시 redirect 거부 및 5MB 초과 시 response size 제한 에러 검증 |
| `test_llm_client_uses_120_second_timeout` | NFR-5-1 | HTTP LLMClient의 타임아웃이 120초로 적용되어 동작하는지 검증 |
| `test_action_failure_preserves_partial_workspace` | BR-5-10 | 액션 수행 중 중간 실패 시 이미 작성된 파일 workspace에 보존 및 FAILED 상태 전이 검증 |
| `test_stale_running_jobs_recovered_at_startup` | NFR-5-7 | lifespan 기동 시 15분 초과 stale RUNNING Job을 FAILED 상태로 자동 복구하고 감사 로그 적재 검증 |

---

## 실패 시 조치 방법

```bash
# 상세 오류 출력으로 재실행
pytest tests/ -v --tb=long

# 첫 번째 실패에서 중단
pytest tests/ -x

# 특정 테스트만 격리 실행
pytest tests/test_unit_3.py::test_timeout_kills_process -v -s
```
