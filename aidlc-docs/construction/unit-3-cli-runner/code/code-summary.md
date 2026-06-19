# 코드 생성 요약 (Code Summary) - Unit 3: CLI Runner Service

> 생성 완료 일시: 2026-06-19T11:05:00+09:00  
> 테스트 결과: **17/17 통과** (Unit 1 + Unit 2 + Unit 3 전체 회귀 테스트 포함)

---

## 생성된 파일 목록

| 파일 | 액션 | 역할 |
|------|------|------|
| [`runner/exceptions.py`](file:///d:/workspace/CLI-Execution-Platform/runner/exceptions.py) | 신규 생성 | CLI 예외 계층 (`CLIExecutionError`, `CLIExecutionLaunchError`, `CLIExecutionTimeoutError`, `CLIArgumentValidationError`) |
| [`runner/validator.py`](file:///d:/workspace/CLI-Execution-Platform/runner/validator.py) | 신규 생성 | `ArgumentValidator` — Allowlist 정규식 기반 인자 검증 |
| [`runner/service.py`](file:///d:/workspace/CLI-Execution-Platform/runner/service.py) | 신규 생성 | `CLIExecutionRunner` — 핵심 실행 오케스트레이터 (전 NFR 패턴 통합) |
| [`runner/__init__.py`](file:///d:/workspace/CLI-Execution-Platform/runner/__init__.py) | 신규 생성 | 패키지 공개 API 노출 |
| [`tests/test_unit_3.py`](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_3.py) | 신규 생성 | 통합 테스트 8개 |

---

## 구현된 NFR 패턴 요약

| NFR | 패턴 | 구현 위치 |
|-----|------|---------|
| NFR-1.1 (30초 타임아웃) | `asyncio.wait_for(timeout=30)` + `process.kill()` | `service.py:_execute_with_timeout` |
| NFR-1.2 (동시 실행 max 2) | `asyncio.Semaphore(2)` 모듈 레벨 전역 싱글턴 | `service.py:_CLI_SEMAPHORE` |
| NFR-1.3 (기동 실패 재시도) | OSError 한정 최대 2회, 0.1~0.5s Jitter | `service.py:_launch_with_retry` |
| NFR-1.4 (Shell Injection 차단) | Allowlist 정규식 `^[a-zA-Z0-9_./:=,\-]+$` | `validator.py:ArgumentValidator` |
| Q2 (청크 단위 수집) | 4KB 청크 + line_buffer | `service.py:_collect_streams` |
| Q4 (타임아웃 부분 출력 보존) | 기존 EventLog 보존 + SYSTEM_EVENT 마커 | `service.py:_write_system_marker` |

---

## 요구사항 검증 결과 (Requirement Verification Evidence)

| NFR ID | 요구사항 | 테스트 함수 | 결과 |
|--------|---------|-----------|------|
| NFR-1.1 | 30초 타임아웃 | `test_timeout_kills_process` | ✅ PASS |
| NFR-1.2 | 동시 실행 max 2 | `test_semaphore_limits_concurrency` | ✅ PASS |
| NFR-1.3 | 기동 실패 재시도 | `test_launch_retry_on_os_error` | ✅ PASS |
| NFR-1.4 | Shell Injection 차단 | `test_argument_validation_blocks_unsafe_chars` | ✅ PASS |
| NFR-1.4 | 안전한 인자 통과 | `test_argument_validation_allows_safe_args` | ✅ PASS |
| Q2 | 청크 수집 + EventLog DB 저장 | `test_run_tool_success_writes_event_logs` | ✅ PASS |
| Q4 | 타임아웃 부분 출력 보존 | `test_timeout_preserves_partial_logs` | ✅ PASS |
| US-3-1 | Non-Zero Exit Code 예외 | `test_nonzero_exit_code_raises_cli_execution_error` | ✅ PASS |

---

## 전체 테스트 회귀 결과

```
tests/test_unit_1.py  4/4  PASS
tests/test_unit_2.py  5/5  PASS
tests/test_unit_3.py  8/8  PASS
─────────────────────────────
합계              17/17  PASS (회귀 없음)
```

---

## N/A 항목

없음 — 모든 NFR 및 스토리 검증 항목이 자동화 테스트로 커버되었습니다.
