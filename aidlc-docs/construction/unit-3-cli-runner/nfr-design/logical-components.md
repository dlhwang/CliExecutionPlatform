# 논리 컴포넌트 정의서 - Unit 3: CLI Runner Service

> 본 문서는 `nfr-design-patterns.md`에 정의된 비기능 설계 패턴을 구체적인 논리 컴포넌트,
> 인터페이스, 내부 상태, 그리고 컴포넌트 간 협력 관계로 명세합니다.

---

## 1. 컴포넌트 목록 개요

```
Unit 3: CLI Runner Service
├── CLIExecutionRunner          (핵심 오케스트레이터)
├── ArgumentValidator           (보안: Allowlist 검증)
├── SubprocessLauncher          (프로세스 기동 + 재시도)
├── StreamCollector             (청크 단위 스트림 수집)
├── EventLogWriter              (EventLog DB 저장)
├── TimeoutGuard                (30초 데드라인 강제)
├── SemaphoreGuard              (전역 동시성 제한)
└── ExecutionError              (예외 계층)
```

---

## 2. 전역 공유 자원

### 2.1 `_CLI_SEMAPHORE` (Module-Level Singleton)

```python
# runner.py 모듈 레벨에 선언
import asyncio

_CLI_SEMAPHORE: asyncio.Semaphore = asyncio.Semaphore(2)
```

| 속성 | 값 |
|------|---|
| 타입 | `asyncio.Semaphore` |
| 초기 허가 수 | 2 |
| 스코프 | 프로세스 전역 (모듈 임포트 시 단일 인스턴스) |
| 대기 정책 | 무한 대기 (타임아웃 없음) |

---

## 3. 컴포넌트 상세 명세

### 3.1 `CLIExecutionRunner`

**역할**: 전체 CLI 실행 워크플로우의 오케스트레이터. 모든 NFR 패턴의 진입점.

**인터페이스**:

```python
class CLIExecutionRunner:
    def __init__(
        self,
        db: AsyncSession,
        semaphore: asyncio.Semaphore = _CLI_SEMAPHORE
    ): ...

    async def execute(
        self,
        job_id: UUID,
        tool_binary: str,
        args: list[str],
        workspace_path: Path,
        timeout_seconds: float = 30.0
    ) -> ExecutionResult: ...
```

**실행 워크플로우**:

```
execute() 호출
  │
  ├─ 1. ArgumentValidator.validate(args)          ← 보안 검증 (실패 시 즉시 예외)
  │
  ├─ 2. async with SemaphoreGuard(_CLI_SEMAPHORE) ← 동시성 제한 (대기)
  │   │
  │   ├─ 3. SubprocessLauncher.launch(...)        ← 프로세스 기동 (재시도 포함)
  │   │
  │   ├─ 4. TimeoutGuard.wrap(                    ← 30초 데드라인
  │   │       StreamCollector.collect(process)    ← 청크 스트림 수집
  │   │       EventLogWriter.write(records)       ← DB 저장
  │   │   )
  │   │
  │   └─ 5. process.wait() + 종료 코드 확인
  │
  └─ 6. ExecutionResult 반환
```

**반환 타입**:

```python
@dataclass
class ExecutionResult:
    exit_code: int
    timed_out: bool
    total_lines: int
    launch_attempts: int
```

---

### 3.2 `ArgumentValidator`

**역할**: CLI 인자 목록에 대한 Allowlist 정규식 검증 수행.

**인터페이스**:

```python
class ArgumentValidator:
    SAFE_ARG_PATTERN: re.Pattern = re.compile(r'^[a-zA-Z0-9_./:=,\-]+$')

    @classmethod
    def validate(cls, args: list[str]) -> None:
        """
        각 인자가 SAFE_ARG_PATTERN에 매칭되지 않으면
        CLIArgumentValidationError를 발생시킵니다.
        """
        ...
```

**예외**:

```python
class CLIArgumentValidationError(ValueError):
    """Allowlist 정규식에 매칭되지 않는 인자 검출 시 발생"""
    def __init__(self, offending_arg: str): ...
```

**입력/출력**:

| 항목 | 값 |
|------|---|
| 입력 | `args: list[str]` |
| 성공 | `None` 반환 (통과) |
| 실패 | `CLIArgumentValidationError` 발생 |
| 부작용 | 없음 (순수 함수) |

---

### 3.3 `SubprocessLauncher`

**역할**: `asyncio.create_subprocess_exec` 호출을 담당하며, OS 에러 발생 시 최대 2회 재시도 로직을 내장합니다.

**인터페이스**:

```python
class SubprocessLauncher:
    MAX_RETRIES: int = 2
    JITTER_MIN: float = 0.1
    JITTER_MAX: float = 0.5

    async def launch(
        self,
        binary: str,
        args: list[str],
        cwd: Path,
    ) -> tuple[asyncio.subprocess.Process, int]:
        """
        Returns: (process, attempt_count)
        attempt_count는 1(최초 성공) ~ 3(2회 재시도 후 성공)
        """
        ...
```

**재시도 정책**:

| 회차 | 조건 | 대기 | 결과 |
|------|------|------|------|
| 1회차 (최초) | OSError | - | 재시도 진행 |
| 2회차 | OSError | 0.1~0.5s Jitter | 재시도 진행 |
| 3회차 | OSError | 0.1~0.5s Jitter | `CLIExecutionLaunchError` 발생 |
| 임의 회차 | 성공 | - | `(process, attempt_count)` 반환 |

**예외**:

```python
class CLIExecutionLaunchError(RuntimeError):
    """최대 재시도 횟수 초과 후에도 프로세스 기동 실패 시 발생"""
    def __init__(self, attempts: int, last_error: OSError): ...
```

---

### 3.4 `StreamCollector`

**역할**: subprocess의 stdout/stderr를 4KB 청크 단위로 수집하고, 줄(line) 단위로 분할하여 `EventLog` DTO 목록을 생성합니다.

**인터페이스**:

```python
class StreamCollector:
    CHUNK_SIZE: int = 4096

    async def collect(
        self,
        process: asyncio.subprocess.Process,
        job_id: UUID,
        on_records: Callable[[list[EventLogDTO]], Awaitable[None]]
    ) -> int:
        """
        stdout/stderr 수집 완료 시 총 수집 줄 수 반환.
        청크 완성 시마다 on_records 콜백을 통해 EventLogWriter에게 전달.
        """
        ...
```

**내부 상태**:

```python
# 컬렉터 내부에서 유지되는 라인 버퍼 (청크 경계에서 잘린 부분 줄 처리용)
_stdout_buffer: bytes = b""
_stderr_buffer: bytes = b""
_seq_counter: int = 0
```

**EventLog DTO**:

```python
@dataclass
class EventLogDTO:
    job_id: UUID
    seq: int          # 단조 증가 시퀀스 번호
    stream: str       # "stdout" | "stderr" | "system"
    line: str         # UTF-8 디코딩된 줄 내용 (errors="replace")
    ts: datetime      # 수집 시각 (UTC)
```

---

### 3.5 `EventLogWriter`

**역할**: `EventLogDTO` 목록을 `EventLog` ORM 모델로 변환하여 DB에 일괄 INSERT합니다.

**인터페이스**:

```python
class EventLogWriter:
    def __init__(self, db: AsyncSession): ...

    async def write(self, records: list[EventLogDTO]) -> None:
        """
        records를 EventLog ORM 객체로 변환하여 db.add_all() + commit().
        """
        ...

    async def write_marker(
        self,
        job_id: UUID,
        seq: int,
        marker_type: str,   # "TIMEOUT" | "LAUNCH_FAILED" | "COMPLETE"
        message: str
    ) -> None:
        """
        시스템 마커 레코드를 stream="system"으로 EventLog에 기록.
        """
        ...
```

---

### 3.6 `TimeoutGuard`

**역할**: `asyncio.wait_for`를 래핑하여 30초 데드라인을 강제하고, 타임아웃 시 프로세스 종료 및 TIMEOUT 마커 기록을 처리합니다.

**인터페이스**:

```python
class TimeoutGuard:
    def __init__(
        self,
        timeout_seconds: float,
        process: asyncio.subprocess.Process,
        writer: EventLogWriter,
        job_id: UUID,
    ): ...

    async def run(self, coro: Coroutine) -> None:
        """
        coro를 timeout_seconds 이내에 실행.
        TimeoutError 발생 시:
          1. process.kill() 호출
          2. await process.wait()
          3. EventLogWriter.write_marker(TIMEOUT) 호출
          4. CLIExecutionTimeoutError 재발생
        """
        ...
```

**예외**:

```python
class CLIExecutionTimeoutError(RuntimeError):
    """30초 타임아웃 초과 후 프로세스 강제 종료 시 발생"""
    def __init__(self, job_id: UUID, timeout_seconds: float): ...
```

---

### 3.7 예외 계층 (`ExecutionError`)

```
Exception
└── RuntimeError
    ├── CLIExecutionLaunchError       # 프로세스 기동 실패 (재시도 초과)
    └── CLIExecutionTimeoutError      # 30초 타임아웃 초과
└── ValueError
    └── CLIArgumentValidationError    # Allowlist 검증 실패
```

---

## 4. 컴포넌트 협력 다이어그램

```
 ┌─────────────────────────────────────────────────────┐
 │              CLIExecutionRunner                      │
 │                                                     │
 │  1. ArgumentValidator.validate(args)                │
 │  2. async with _CLI_SEMAPHORE (SemaphoreGuard)      │
 │     3. SubprocessLauncher.launch()  ──→ Process     │
 │     4. TimeoutGuard.run(                            │
 │          StreamCollector.collect(                   │
 │            process,                                 │
 │            on_records=EventLogWriter.write          │
 │          )                                          │
 │        )                                            │
 │     5. process.wait()                               │
 │  6. return ExecutionResult                          │
 └─────────────────────────────────────────────────────┘
         │              │              │
         ▼              ▼              ▼
  ArgumentValidator  SubprocessLauncher  StreamCollector
  (Allowlist 검증)   (OSError 재시도)    (4KB 청크 수집)
                                         │
                                         ▼
                                   EventLogWriter
                                   (DB INSERT)
                                         │
                                         ▼
                                   [EventLog Table]
```

---

## 5. 파일 구조 (예정)

```
cli/
├── runner.py           # CLIExecutionRunner + _CLI_SEMAPHORE
├── launcher.py         # SubprocessLauncher
├── validator.py        # ArgumentValidator
├── collector.py        # StreamCollector + EventLogDTO
├── writer.py           # EventLogWriter
├── timeout_guard.py    # TimeoutGuard
└── errors.py           # CLIExecutionLaunchError, CLIExecutionTimeoutError,
                        # CLIArgumentValidationError
```

---

## 6. NFR 요구사항 추적성 매트릭스

| NFR ID | 요구사항 | 담당 컴포넌트 | 패턴 |
|--------|---------|-------------|------|
| NFR-1.1 | 30초 타임아웃 | `TimeoutGuard` | Deadline-Enforced Subprocess |
| NFR-1.2 | 동시 실행 max 2 | `_CLI_SEMAPHORE` | Global Semaphore Guard |
| NFR-1.3 | 기동 실패 재시도 | `SubprocessLauncher` | Bounded Backoff Retry |
| NFR-1.4 | Shell Injection 방지 | `ArgumentValidator` | Argument Allowlist Validation |
| Q2 결정 | 청크 단위 스트림 수집 | `StreamCollector` | Chunked Buffer Accumulation |
| Q4 결정 | 타임아웃 부분 출력 보존 | `TimeoutGuard` + `EventLogWriter` | Partial Log Preservation |
