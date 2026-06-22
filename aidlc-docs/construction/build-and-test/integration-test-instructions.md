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

---

## R-14 Docker Compose 통합 시나리오

### 시나리오 1: App Container <-> DB Container 연동 (Docker Compose 내 PostgreSQL 연동)

- `.env`에 정의된 `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`를 기반으로 `db` 서비스(PostgreSQL 16-alpine)가 자동으로 백그라운드 구동됩니다.
- `app` 서비스는 `db` 서비스의 pg_isready 헬스체크가 성공 상태가 될 때까지 기동을 대기(depends_on)하고, 기동 후 `DATABASE_URL`을 통해 도커 내부 네트워크(`db:5432`)로 자동 연결됩니다.
- `docker compose up -d` 후 startup log에 DB 연결 오류가 없어야 합니다.

### 시나리오 2: Job Workspace -> OpenSCAD 격리 실행 -> Subdirectory stl 결과물 복사 및 보존

1. OpenSCAD 버전을 확인한다.
2. `POST /api/v1/jobs`에 하위 디렉토리를 출력 경로로 정의하는 유효한 prompt를 전송한다. (예: `dice_design/octahedron_dice.stl` 출력 요청)
3. 서버 내부적으로 OpenSCAD CLI가 호스트의 마운트 폴더가 아닌 `/tmp` 임시 격리 경로 상에서 실행되는지 확인한다.
4. 실행 중 `/tmp` 하위에 `dice_design` 부모 디렉토리가 생성되고 `octahedron_dice.stl` 파일이 정상 빌드되는지 확인한다.
5. 실행 전/후 파일 스냅샷 비교 방식을 거쳐 `dice_design/octahedron_dice.stl` 파일이 호스트 볼륨에 마운트된 `/app/.workspaces/jobs/{job_id}/dice_design/octahedron_dice.stl` 경로로 최종 복사되는지 확인한다.
6. `docker compose logs app`에서 오류 traceback이나 `is not a directory` 스킵 경고가 없는지 확인한다.

```bash
docker compose exec app /usr/local/bin/openscad-headless --version
curl -X POST http://localhost:8000/api/v1/jobs \
  -H 'Content-Type: application/json' \
  -d '{"prompt":"Create a dice model in dice_design/octahedron_dice.stl"}'
docker compose logs app
```

### 시나리오 3: Workspace Volume 및 Database Volume 보존

```bash
docker compose down
docker compose up -d
```

- 컨테이너 재기동 후에도 `postgres_data` 볼륨 덕분에 기존 생성된 Job 메타데이터가 보존되어야 합니다.
- 호스트 바인드 마운트된 `tests/` 및 `.workspaces/` 내의 이전 Job workspace 파일들과 생성된 STL 결과물들이 손실 없이 유지되는지 확인한다. `down -v`는 named volume과 DB 데이터를 영구 삭제하므로 사용하지 않습니다.

### 현재 실행 상태

현재 검증 환경에는 Docker CLI와 설치된 WSL 배포판이 없어 위 3개 container 통합 시나리오는 N/A입니다. WSL2 또는 Linux Docker 환경에서 필수 후속 검증으로 수행해야 합니다.

---

## R-15A/B/C 통합 시나리오

### 시나리오 1: Runner diagnostics → LLM retry

- 첫 OpenSCAD 실행에서 `Current top level object is empty.` 또는 2D/3D 혼용 경고와 exit code 1을 발생시킵니다.
- `CLIExecutionError`는 bounded stdout/stderr tail만 보유해야 합니다.
- 다음 LLM 요청은 해당 Rule ID가 포함된 현재 attempt feedback만 받아야 합니다.
- 검증: `test_orchestrator_runtime_refinement_rolls_back_and_persists_only_final_plan`

### 시나리오 2: Failed attempt rollback → final artifact promotion

- 첫 attempt가 workspace 파일을 작성한 뒤 CLI에서 실패하도록 합니다.
- workspace와 artifact 저장소가 attempt 이전 상태로 복구되는지 확인합니다.
- 두 번째 성공 attempt의 파일과 artifact만 남고 해당 plan만 DB에 저장되는지 확인합니다.
- 검증: `test_orchestrator_runtime_refinement_rolls_back_and_persists_only_final_plan`

### 시나리오 3: Retry exhaustion → bounded FAILED

- 세 번의 실행 attempt를 모두 실패시킵니다.
- Job은 `FAILED`로 전이하고 action plan은 저장되지 않아야 합니다.
- 실패 이벤트는 bounded reason만 포함해야 합니다.
- 검증: `test_runtime_retry_exhaustion_fails_with_bounded_reason`
