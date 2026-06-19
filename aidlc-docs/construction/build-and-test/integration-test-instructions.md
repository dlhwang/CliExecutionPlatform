# 통합 테스트 지침서 (Integration Test Instructions)

## 목적

유닛 간 인터페이스 계층의 상호작용이 올바르게 동작하는지 검증합니다.
본 프로젝트는 현재 단일 FastAPI 모놀리스 구조이며, 각 유닛 테스트가 SQLite 인메모리 DB 및
Mock을 통해 다른 유닛의 실제 구현체를 호출하는 통합 시나리오를 포함합니다.

---

## 통합 시나리오 목록

### 시나리오 1: Unit 1 → Unit 2 통합 (Job 생성 → LLM 파서 연동)

- **설명**: Job 생성 API 응답 후 `action_plan` JSON이 `ActionPlanParser`를 통해 파싱되어 Pydantic 모델로 변환되는 흐름 검증
- **현재 커버**: `test_json_extraction_success` (Unit 2 테스트에서 Unit 1의 `ActionType` 스키마 실제 사용)
- **검증 포인트**: `CreateDirectoryAction`, `WriteFileAction`, `RunToolAction`, `CreateArtifactAction`이 정확히 구분되는지

### 시나리오 2: Unit 2 → Unit 3 통합 (보안 검증 → CLI 실행)

- **설명**: `SecurityPolicyValidator`가 `RUN_TOOL` 액션의 `tool_name`을 검증한 후 `CLIExecutionRunner`가 실행 인자를 Allowlist 재검증하는 이중 방어 체계 검증
- **현재 커버**: `test_security_validator_tool_whitelist` + `test_argument_validation_blocks_unsafe_chars`
- **검증 포인트**: openscad만 허용되고, 실행 전 인자 Allowlist 2중 차단이 독립적으로 동작함을 확인

### 시나리오 4: Unit 1 / Unit 3 → Unit 4 통합 (EventLog DB 적재 → SSE 스트리밍)

- **설명**: CLI Runner나 시스템 이벤트에 의해 적재된 EventLog가 SSE 스트리밍을 통해 Last-Event-ID 기준으로 정밀하게 복원되어 클라이언트에 실시간 푸시되는 흐름 검증
- **현재 커버**: `test_sse_streaming_completed_job`, `test_sse_catchup_after_last_event_id`
- **검증 포인트**: 데이터베이스에서 순서대로 읽은 이벤트가 적합한 JSON 형태 및 `text/event-stream` 프로토콜로 누락 없이 전송됨

### 시나리오 5: Unit 1 / 2 / 3 / 4 → Unit 5 통합 (오케스트레이션 및 refinement 전체 루프)

- **설명**: Refinement API 요청 시 이전 완료 Job의 Workspace 파일을 복사하고, LLM을 통해 액션 계획을 생성·검증(Parser/Validator)한 뒤 순차 실행(Runner)하며 SSE로 진행 이벤트를 스트리밍하는 전체 통합 흐름 검증
- **현재 커버**: `test_refinement_copies_context_and_calls_llm`, `test_action_failure_preserves_partial_workspace`
- **검증 포인트**: CREATED -> RUNNING -> COMPLETED/FAILED 상태 전이 및 부분 실패 시 workspace 보존, parent-child 계보 DB 추적

---

## 통합 테스트 환경 설정

### 테스트 DB (SQLite 인메모리 — 별도 구성 불필요)

```bash
# conftest.py의 db_session 픽스처가 자동으로 처리
# 테스트 시작 시 테이블 생성, 종료 시 자동 정리
pytest tests/ -v
```

### 실제 PostgreSQL 연동 통합 테스트 (선택 사항)

```bash
# .env의 DATABASE_URL을 실제 PostgreSQL로 설정 후
export DATABASE_URL=postgresql://user:pass@localhost:5432/cli_platform_test
pytest tests/ -v
```

---

## 통합 테스트 실행

### 전체 통합 테스트 실행

```bash
# 현재 모든 테스트가 통합 시나리오를 포함
pytest tests/ -v
```

### 통합 시나리오 집중 실행

```bash
# Unit 1 ↔ Unit 2 연동 시나리오
pytest tests/test_unit_2.py -v -k "security_validator"

# Unit 1 ↔ Unit 3 EventLog 연동 시나리오
pytest tests/test_unit_3.py -v -k "event_logs or partial_logs"
```

---

## 통합 테스트 결과 (실측)

| 시나리오 | 관련 테스트 | 결과 |
|---------|-----------|------|
| Unit 1 → Unit 2 (스키마 통합) | `test_json_extraction_success` | ✅ PASS |
| Unit 2 보안 검증 → DB 감사 로그 | `test_security_validator_path_protection` | ✅ PASS |
| Unit 2 Tool Whitelist → Unit 3 Allowlist 이중 방어 | `test_security_validator_tool_whitelist` + `test_argument_validation_*` | ✅ PASS |
| Unit 3 → EventLog DB 적재 (Unit 1 ORM) | `test_run_tool_success_writes_event_logs` | ✅ PASS |
| Unit 3 타임아웃 → 부분 EventLog 보존 | `test_timeout_preserves_partial_logs` | ✅ PASS |
| Unit 1 / Unit 3 → Unit 4 (DB 적재 → SSE 스트리밍 연동) | `test_sse_streaming_completed_job`, `test_sse_catchup_after_last_event_id` | ✅ PASS |
| Unit 1 / 2 / 3 / 4 → Unit 5 (오케스트레이션 및 refinement 루프 통합) | `test_refinement_copies_context_and_calls_llm`, `test_action_failure_preserves_partial_workspace` | ✅ PASS |

---

## 정리 (Cleanup)

SQLite 인메모리 DB 사용으로 별도 정리 작업 불필요. 각 테스트 종료 시 자동 DROP.

```bash
# .workspaces 임시 파일 정리 (필요 시)
rm -rf .workspaces/
```
