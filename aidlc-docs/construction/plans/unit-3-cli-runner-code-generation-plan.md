# 코드 생성 계획서 (Code Generation Plan) - Unit 3: CLI Runner Service

> 본 계획서는 Unit 3 CLI Runner Service의 코드 생성을 위한 단일 정보 출처(Single Source of Truth)입니다.
> 모든 코드 생성 작업은 이 계획서에 명시된 단계를 순서대로 따릅니다.

---

## 유닛 컨텍스트 (Unit Context)

| 항목 | 내용 |
|------|------|
| **유닛명** | Unit 3: CLI Runner Service |
| **프로젝트 유형** | Greenfield / Monolith |
| **코드 위치** | `d:\workspace\CLI-Execution-Platform\runner\` |
| **테스트 위치** | `d:\workspace\CLI-Execution-Platform\tests\test_unit_3.py` |
| **문서 위치** | `aidlc-docs/construction/unit-3-cli-runner/code/` |
| **주요 의존성** | Unit 1 (EventLog ORM), Unit 2 (SecurityPolicyValidator) |

---

## 담당 유저 스토리 (Story Traceability)

| 스토리 ID | 내용 | 구현 단계 |
|----------|------|---------|
| US-3-1 | CLI 실행 서비스는 `asyncio.create_subprocess_exec`으로 OpenSCAD를 가동한다 | Step 3 |
| US-3-2 | 30초 타임아웃 초과 시 프로세스를 강제 종료하고 예외를 발생시킨다 | Step 3 |
| US-3-3 | Semaphore(2)로 최대 동시 실행 수를 2개로 제한한다 | Step 3 |
| US-3-4 | 프로세스 기동 실패 시 최대 2회 재시도한다 | Step 3 |
| US-3-5 | 인자 Allowlist 검증을 통해 Shell Injection을 차단한다 | Step 2 |
| US-3-6 | stdout/stderr 출력을 4KB 청크 단위로 수집하여 EventLog에 저장한다 | Step 3 |

---

## 요구사항 검증 매핑 (Requirement Verification Mapping)

| NFR ID | 요구사항 | 검증 테스트 |
|--------|---------|-----------|
| NFR-1.1 | 30초 타임아웃 | `test_timeout_kills_process` |
| NFR-1.2 | 동시 실행 max 2 | `test_semaphore_limits_concurrency` |
| NFR-1.3 | 기동 실패 재시도 | `test_launch_retry_on_os_error` |
| NFR-1.4 | Shell Injection 차단 | `test_argument_validation_blocks_unsafe_chars` |
| Q2 | 청크 수집 + EventLog 저장 | `test_stream_collector_writes_event_logs` |
| Q4 | 타임아웃 시 부분 출력 보존 | `test_timeout_preserves_partial_logs` |

---

## 생성 단계 체크리스트

### Step 1: 예외 클래스 생성
- [x] `runner/exceptions.py` 신규 생성
  - `CLIExecutionError` (기본 예외, `exit_code` 속성)
  - `CLIExecutionLaunchError` (`target_path` 속성, 재시도 초과 시 발생)
  - `CLIExecutionTimeoutError` (`timeout_limit` 속성)
  - `CLIArgumentValidationError` (`offending_arg` 속성)

### Step 2: 인자 검증기 생성
- [x] `runner/validator.py` 신규 생성
  - `ArgumentValidator` 클래스
  - `SAFE_ARG_PATTERN = re.compile(r'^[a-zA-Z0-9_./:=,\-]+$')`
  - `validate(cls, args: list[str]) -> None` 클래스 메서드
  - Allowlist 불일치 시 `CLIArgumentValidationError` 발생

### Step 3: 핵심 실행 서비스 생성
- [x] `runner/service.py` 신규 생성
  - 모듈 레벨 `_CLI_SEMAPHORE = asyncio.Semaphore(2)` 선언
  - `CLIExecutionRunner` 클래스
  - `__init__(self, base_dir: Path | str | None = None)` — `.env` OPENSCAD_BIN_PATH 로드
  - `run_tool(job_id, tool_name, args, db)` async 메서드

### Step 4: `runner/__init__.py` 생성
- [x] `runner/__init__.py` 신규 생성 (패키지 초기화, 공개 API 노출)

### Step 5: 통합 테스트 파일 생성
- [x] `tests/test_unit_3.py` 신규 생성 (8개 테스트 — 전 NFR 검증, 17/17 통과)

### Step 6: 코드 요약 문서 생성
- [x] `aidlc-docs/construction/unit-3-cli-runner/code/code-summary.md` 생성

---

## 의존성 및 제약 사항

- Python `asyncio` 표준 라이브러리 (외부 라이브러리 불필요)
- `sqlalchemy.orm.Session` (동기식 DB 세션, Unit 1 기반)
- `.env` 파일의 `OPENSCAD_BIN_PATH` 설정 (없으면 기본값 `"openscad"`)
- 테스트는 실제 OpenSCAD CLI **불필요** — 크로스 플랫폼 호환 명령어(`python -c`, `echo`)로 대체

---

## 총 생성 파일 수

| 파일 | 유형 | 액션 |
|------|------|------|
| `runner/exceptions.py` | 애플리케이션 코드 | 신규 생성 |
| `runner/validator.py` | 애플리케이션 코드 | 신규 생성 |
| `runner/service.py` | 애플리케이션 코드 | 신규 생성 |
| `runner/__init__.py` | 애플리케이션 코드 | 신규 생성 |
| `tests/test_unit_3.py` | 테스트 코드 | 신규 생성 |
| `aidlc-docs/.../code-summary.md` | 문서 | 신규 생성 |

**총 6개 파일 신규 생성**
