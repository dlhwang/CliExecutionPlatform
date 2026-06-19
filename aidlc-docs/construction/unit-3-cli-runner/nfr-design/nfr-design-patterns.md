# NFR 설계 패턴 정의서 - Unit 3: CLI Runner Service

> 본 문서는 `nfr-requirements.md`에서 확정된 비기능 요구사항과 NFR Design Plan의 사용자 답변을 토대로,
> **CLI Runner Service**에 적용할 비기능 설계 패턴을 구체적으로 정의합니다.

---

## 1. 타임아웃 및 프로세스 생명주기 패턴

### 1.1 패턴명: Deadline-Enforced Subprocess Pattern

**근거**: NFR 1.1 (최대 프로세스 실행 타임아웃: 30초)

**설계 원칙**:
- `asyncio.wait_for(coro, timeout=30)` 래퍼를 사용하여 subprocess 실행 전체에 30초 데드라인을 부여합니다.
- 타임아웃 발생 시 `asyncio.TimeoutError`를 포착하여 `asyncio.subprocess.Process.kill()`을 즉시 호출하고 운영체제 수준의 프로세스 자원을 회수합니다.
- `kill()` 이후 `await process.wait()`를 반드시 호출하여 좀비 프로세스 발생을 방지합니다.

**타임아웃 시 처리 흐름**:

```
asyncio.TimeoutError 발생
  → process.kill() 호출 (SIGKILL)
  → await process.wait() (좀비 방지)
  → 수집된 부분 EventLog 레코드는 보존 (Q4: Option A)
  → EventLog에 TIMEOUT 마커 레코드 추가 INSERT
  → Job 상태를 FAILED (reason=TIMEOUT) 로 업데이트
  → CLIExecutionTimeoutError 예외 상위 전파
```

**타임아웃 마커 레코드 구조**:

```python
EventLog(
    job_id=job_id,
    seq=<last_seq + 1>,
    stream="system",
    line="[SYSTEM] Process killed: execution exceeded 30s timeout",
    ts=datetime.utcnow()
)
```

---

## 2. 동시성 제어 패턴

### 2.1 패턴명: Global Semaphore Guard Pattern

**근거**: NFR 1.2 (최대 동시 CLI 프로세스 실행 수: 2개), Q5 (프로세스 전역 단일 Semaphore), Q1 (무한 대기 허용)

**설계 원칙**:
- FastAPI 애플리케이션 구동 시점에 **프로세스 전역 단일 `asyncio.Semaphore(2)`** 인스턴스를 생성하여 모듈 레벨 싱글턴으로 유지합니다.
- 모든 CLI 실행 요청은 `async with _CLI_SEMAPHORE:` 블록 진입 전까지 이벤트 루프에서 비동기 대기 상태로 머뭅니다 (무한 대기 허용).
- Semaphore 스코프는 Tool 종류에 무관하게 전역 공유 (MVP 단순성 우선).

**구현 구조**:

```python
# runner.py (module level)
_CLI_SEMAPHORE = asyncio.Semaphore(2)

class CLIExecutionRunner:
    async def execute(self, job_id: UUID, plan: ActionPlan) -> ExecutionResult:
        async with _CLI_SEMAPHORE:          # 최대 2개 동시 실행 보장
            return await self._run_process(job_id, plan)
```

**동시성 흐름 다이어그램**:

```
Request 1 ──→ [acquire Semaphore] ──→ 실행 중 ──→ [release]
Request 2 ──→ [acquire Semaphore] ──→ 실행 중 ──→ [release]
Request 3 ──→ [대기: Semaphore 포화] ──────────────→ [Request 1 또는 2 완료 후 acquire] → 실행
```

---

## 3. 신뢰성 패턴

### 3.1 패턴명: Bounded Exponential Backoff Retry (Launch-Only)

**근거**: NFR 1.3 (프로세스 기동 실패 시 최대 2회 재시도)

**설계 원칙**:
- `asyncio.create_subprocess_exec` 호출 자체가 `OSError`를 발생시키는 경우(파일시스템 락, OS 스케줄링 거부 등)에만 재시도를 적용합니다.
- 재시도는 최대 2회, 회차별 대기 시간은 `random.uniform(0.1, 0.5)` 초의 지터(Jitter)를 적용하여 재실행 충돌을 분산시킵니다.
- 프로세스가 성공적으로 기동된 이후 발생하는 오류(Timeout, Non-Zero Exit Code)는 재시도 대상이 **아닙니다**.
- 2회 재시도 모두 실패 시 `CLIExecutionLaunchError`를 발생시켜 상위 레이어로 전파합니다.

**재시도 의사코드**:

```python
MAX_LAUNCH_RETRIES = 2

for attempt in range(MAX_LAUNCH_RETRIES + 1):
    try:
        process = await asyncio.create_subprocess_exec(...)
        break  # 기동 성공
    except OSError as e:
        if attempt == MAX_LAUNCH_RETRIES:
            raise CLIExecutionLaunchError(...) from e
        await asyncio.sleep(random.uniform(0.1, 0.5))
```

---

## 4. 보안 패턴

### 4.1 패턴명: Argument Allowlist Validation Pattern

**근거**: NFR 1.4 (shell=True 금지, 쉘 제어 특수기호 차단), Q3 (Allowlist 정규식 방식 선택)

**설계 원칙**:
- 실행 인자(`args`) 목록의 각 요소를 허용 패턴(Allowlist 정규식)과 대조하여, 매칭 실패 시 프로세스 실행 전에 즉시 차단합니다.
- `shell=False`를 항상 강제하며 이를 코드상에 명시적으로 기재합니다.
- 허용 패턴은 Tool 종류(e.g., OpenSCAD)별로 정의 가능하도록 설계하되, MVP에서는 공통 기본 패턴을 사용합니다.

**기본 Allowlist 정규식 (OpenSCAD 기준)**:

```python
import re

# 허용 패턴: 영숫자, 경로 구분자, 점, 하이픈, 언더스코어, 등호, 쉼표만 허용
SAFE_ARG_PATTERN = re.compile(r'^[a-zA-Z0-9_./:=,\-]+$')

def validate_args(args: list[str]) -> None:
    for arg in args:
        if not SAFE_ARG_PATTERN.match(arg):
            raise CLIArgumentValidationError(
                f"Unsafe argument detected: {arg!r}"
            )
```

**차단 흐름**:

```
인자 수신
  → 각 인자에 대해 SAFE_ARG_PATTERN.match() 검사
  → 매칭 실패 시 CLIArgumentValidationError 즉시 발생
  → Job 상태 FAILED (reason=INVALID_ARGUMENT) 업데이트
  → 프로세스 실행 없이 중단
```

---

## 5. 스트림 수집 패턴

### 5.1 패턴명: Chunked Buffer Accumulation Pattern

**근거**: Q2 (버퍼 청크 단위 수집 선택)

**설계 원칙**:
- `process.stdout.read(4096)` 및 `process.stderr.read(4096)` 를 반복 호출하여 최대 4KB 단위로 청크를 수집합니다.
- 수집된 청크를 줄 단위로 분할(`splitlines()`)하여 `EventLog` 레코드로 변환하고, 청크 완성 시점에 DB에 일괄 INSERT합니다.
- 이전 청크에서 완전하지 않은 부분 줄(partial line)이 있는 경우 다음 청크와 합산하여 처리하는 `line_buffer`를 유지합니다.

**수집 루프 의사코드**:

```python
CHUNK_SIZE = 4096
line_buffer = b""

while True:
    chunk = await process.stdout.read(CHUNK_SIZE)
    if not chunk:
        break
    line_buffer += chunk
    lines = line_buffer.split(b"\n")
    line_buffer = lines[-1]          # 마지막 미완성 줄 보존
    complete_lines = lines[:-1]
    
    records = [
        EventLog(job_id=job_id, stream="stdout", line=l.decode("utf-8", errors="replace"), ...)
        for l in complete_lines if l
    ]
    db.add_all(records)
    await db.commit()

# 루프 종료 후 잔여 버퍼 처리
if line_buffer:
    db.add(EventLog(..., line=line_buffer.decode("utf-8", errors="replace")))
    await db.commit()
```

---

## 6. 패턴 적용 매트릭스

| NFR 항목 | 적용 패턴 | 핵심 메커니즘 |
|---------|---------|-------------|
| 타임아웃 (30s) | Deadline-Enforced Subprocess | `asyncio.wait_for` + `process.kill()` |
| 동시성 제한 (max 2) | Global Semaphore Guard | `asyncio.Semaphore(2)` 전역 싱글턴 |
| 기동 실패 재시도 (max 2) | Bounded Exponential Backoff Retry | `OSError` 한정 재시도, 0.1~0.5s Jitter |
| Shell Injection 방지 | Argument Allowlist Validation | Allowlist 정규식, `shell=False` 강제 |
| 스트림 수집 | Chunked Buffer Accumulation | 4KB 청크 단위 수집 + 라인 버퍼 |
| 타임아웃 시 부분 출력 | Partial Log Preservation | EventLog 보존 + TIMEOUT 마커 |
