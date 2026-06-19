# 기술 스택 결정서 (Tech Stack Decisions) - Unit 3: CLI Runner Service

본 문서는 **Unit 3: CLI Execution Runner**의 비기능 요구사항을 안전하고 가볍게 실현하기 위한 핵심 기술 스택 및 구동 라이브러리 선정 사유를 기술합니다.

---

## 1. 기술 스택 결정 매트릭스 (Decision Matrix)

| 비기능 요구 영역 | 후보 스택 (Candidates) | 최종 선정 스택 (Chosen) | 선정 Rationale |
| :--- | :--- | :--- | :--- |
| **CLI 비차단 구동** | 1. `subprocess.run` (동기식)<br/>2. `asyncio.subprocess` (비동기식) | **asyncio.create_subprocess_exec** | 비동기 FastAPI 백엔드와 실시간 라인 단위 로그 적재를 매끄럽게 처리하기 위해, 루프를 블로킹하지 않고 스트림을 한 줄씩 `readline()` 할 수 있는 비동기 프로세스 엔진을 채택함. |
| **명령어 보안** | 1. `shell=True` (쉘 제어)<br/>2. `shell=False` (직접 실행) | **Direct Execution (shell=False)** | 외부 쉘 인젝션 벡터를 물리적으로 제거하기 위해, 쉘 해석을 거치지 않는 직접 가동 방식을 적용함. |
| **동시성 임계 제어** | 1. Celery Queue 분리<br/>2. `asyncio.Semaphore` (인메모리) | **asyncio.Semaphore(2)** | MVP의 복잡도를 낮추고 가벼운 서버 구성을 지향하기 위해 별도의 외부 분산 큐 장치 도입 대신, 인메모리 상에서 최대 동시 프로세스 가동 수를 2개로 확실하게 고정할 수 있는 세마포어를 선택함. (YAGNI 및 MVP 원칙 준수) |
| **기동 재시도 정책** | 1. Tenacity 라이브러리 도입<br/>2. 순수 Python try-except 루프 | **Pure Python Loop** | 단순 기동 실패(Launch Fail) 상황에 한정되어 2회만 즉시 실행하는 단순한 흐름이므로, 외부 모듈 도입 오버헤드를 막기 위해 표준 라이브러리 기반의 단순 루프로 가볍게 구성함. |

---

## 2. 세부 설계 영향 및 아키텍처 제약 (Architectural Implications)

1. **비동기 세마포어 전역 관리**:
   - `asyncio.Semaphore`는 싱글 프로세스 내의 비동기 루프 단위에서만 동작하므로, Uvicorn 가동 프로세스 내에서 싱글톤(Singleton) 형태로 인스턴스가 보존되어야 합니다.
   - `CLIExecutionRunner` 인스턴스 또는 의존성 주입 시점에 동일한 세마포어 인스턴스를 참조하도록 전역 생명주기를 설계해야 합니다.
2. **Standard Output 및 Error 병합**:
   - stdout과 stderr를 개별 수집하는 경우, 로깅 순서가 뒤틀리거나 코드가 파편화되어 스레드 간섭이 날 수 있습니다.
   - 따라서 `stderr=asyncio.subprocess.STDOUT` 설정을 강제 적용하여, 하나의 스트림으로 통합 정렬된 로그 시퀀스를 유지하도록 설계합니다.
