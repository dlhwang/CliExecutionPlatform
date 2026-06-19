# 코드 생성 요약 - Unit 5: Iterative Refinement Orchestrator

## 구현 결과

Unit 5는 완료 Job 기반 refinement, 외부 LLM 계획 생성, 전체 플랜 선검증, 네 액션의 직렬 실행, 상태 전이와 stale Job 복구를 통합했습니다.

## 생성 파일

- `orchestrator/__init__.py`
- `orchestrator/config.py`
- `orchestrator/repository.py`
- `orchestrator/recovery.py`
- `orchestrator/concurrency.py`
- `orchestrator/actions.py`
- `orchestrator/service.py`
- `llm/client.py`
- `llm/retry.py`
- `migrations/001_add_parent_job_id.sql`
- `tests/test_unit_5.py`

## 수정 파일

- `jobs/models.py`: `parent_job_id` 자기 참조 관계
- `jobs/schemas.py`: refinement 요청과 부모 ID 응답
- `jobs/service.py`: 부모 사전 검증과 자식 Job 생성
- `jobs/router.py`: refinement API와 실제 BackgroundTask 연결
- `storage/interface.py`, `storage/local.py`: 크기, 존재, 디렉터리, Job 간 복사
- `main.py`: shared HTTP client와 stale recovery lifespan
- `tests/conftest.py`: LLM 설정과 no-op 오케스트레이터 격리

## 주요 동작

- `POST /api/v1/jobs/{previous_job_id}/refine`
- 완료 부모와 두 상속 파일을 API 단계에서 검증
- 5MB 초과 시 자식 Job 없이 HTTP 413
- `httpx.AsyncClient` 기반 120초 LLM 요청
- timeout, 연결, 408, 429, 5xx, JSON 파싱 오류 최대 2회 재시도
- LLM 응답 streaming 5MB 제한과 redirect 거부
- 프로세스당 동시 Job 2개, semaphore 대기 10분
- 상태 전이와 EventLog의 트랜잭션 처리
- 15분 stale `RUNNING` Job 시작 시 실패 전환
- 실패 시 부분 Workspace 보존

## 테스트 결과

| 범위 | 결과 |
|---|---|
| Unit 5 | 12 passed |
| 전체 회귀 | 45 passed |
| Python compile | 통과 |
| UTF-8 BOM | 대상 파일 모두 없음 |
| `git diff --check` | 통과 |

전체 테스트에는 기존 Unit 3 coroutine 관련 경고 2개와 TestClient 폐기 예정 경고 1개가 남아 있으나 실패는 없습니다.

## 추적성 증거

| 요구사항/스토리 | 테스트 | 결과 |
|---|---|---|
| S-5 계보/API | `test_refinement_creates_child_job` | PASS |
| S-5 파일 상속/LLM | `test_refinement_copies_context_and_calls_llm` | PASS |
| BR-5-3, BR-5-5 | `test_refinement_rejects_invalid_parent_or_missing_files` | PASS |
| BR-5-7, BR-5-16 | `test_job_state_transitions_and_duplicate_execution` | PASS |
| BR-5-9, NFR-5-5 | `test_llm_retry_classification_and_backoff` | PASS |
| NFR-5-1 | `test_llm_client_uses_120_second_timeout` | PASS |
| NFR-5-2 | `test_concurrency_gate_limits_two_jobs_and_times_out_waiter` | PASS |
| NFR-5-4 | `test_refinement_rejects_context_over_five_mb`, `test_redirect_and_response_size_are_rejected` | PASS |
| NFR-5-7 | `test_stale_running_jobs_recovered_at_startup` | PASS |
| NFR-5-9, NFR-5-10 | `test_endpoint_security_and_secret_validation` | PASS |
| NFR-5-11 | `test_redirect_and_response_size_are_rejected` | PASS |
| 실패 Workspace 보존 | `test_action_failure_preserves_partial_workspace` | PASS |

## N/A 및 잔여 검증

- 실제 외부 LLM 실호출: 자격 증명과 외부 서비스 의존 때문에 자동화 테스트에서 N/A입니다.
- 기존 PostgreSQL migration 실제 적용: 로컬 PostgreSQL 연결이 필요하므로 최종 Build and Test 지침에서 수동 검증 대상으로 둡니다.
- 다중 프로세스 전역 동시성: MVP 범위 밖입니다.

## 확장 규칙

- Security Baseline: 비활성화되어 N/A
- Property-Based Testing: 비활성화되어 N/A

