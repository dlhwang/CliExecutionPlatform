# NFR 설계 계획 (NFR Design Plan) - Unit 3: CLI Runner Service

> 본 계획은 `aidlc-docs/construction/unit-3-cli-runner/nfr-requirements/nfr-requirements.md`에 정의된
> 비기능 요구사항을 구체적인 설계 패턴 및 논리 컴포넌트로 변환하기 위한 작업 계획서입니다.

---

## 실행 체크리스트

- [x] Step 1: NFR 요구사항 분석
- [x] Step 2: NFR 설계 계획 생성 (현재 문서)
- [x] Step 3: 설계 품질 보강을 위한 질문 수집 및 사용자 답변 대기
- [x] Step 4: 사용자 답변 분석 및 모호성 검토
- [x] Step 5: NFR 설계 산출물 생성
  - [x] `nfr-design-patterns.md` 생성
  - [x] `logical-components.md` 생성
- [ ] Step 6: 완료 메시지 제시 및 사용자 승인 대기
- [ ] Step 7: 승인 기록 및 단계 완료 처리

---

## 분석된 NFR 항목 요약

| 항목 | 요구사항 |
|------|---------|
| 프로세스 타임아웃 | 최대 30초, 초과 시 `kill` 강제 종료 |
| 최대 동시 실행 수 | 2개 (asyncio.Semaphore 활용) |
| 프로세스 기동 실패 재시도 | 최대 2회, 0.1~0.5초 간격의 즉시 재시도 |
| Shell Injection 방지 | `shell=False` + 바이너리+인자 분리 실행 강제 |

---

## 설계 품질 보강 질문 (Step 3)

> NFR 설계의 완성도를 높이기 위한 추가 질문입니다. `[Answer]:` 태그에 답변을 기재해 주십시오.

---

### Q1. [신뢰성 패턴] Semaphore 대기 중인 요청의 타임아웃 처리

현재 NFR 요구사항은 세마포어 대기(queue)에 대한 최대 대기 시간을 명시하지 않습니다.  
동시 실행 수(2개)를 초과하는 3번째 이후 요청이 세마포어를 무한정 대기할 경우, 클라이언트는 응답 없이 멈춰 있게 됩니다.

**선택지:**

- **A. 대기 타임아웃 없음 (무한 대기 허용)** — 먼저 들어온 요청이 끝날 때까지 대기. 구현 단순.
- **B. 대기 타임아웃 설정 (예: 60초)** — 지정 시간 초과 시 `CLIExecutionQueueTimeoutError` 반환.
- **C. 즉시 거절 (Queue 없이 429 반환)** — Semaphore가 꽉 찬 경우 즉시 실패 응답.

[Answer]: A

---

### Q2. [성능 패턴] stdout/stderr 스트림 수집 전략

프로세스 실행 중 발생하는 stdout/stderr 출력을 어떻게 수집할지 결정이 필요합니다.  
이 전략은 메모리 사용량 및 EventLog 쓰기 빈도에 직접 영향을 줍니다.

**선택지:**

- **A. 라인 단위 실시간 수집** — 한 줄씩 읽어 즉시 `EventLog`에 INSERT. SSE 응답성 최대화, DB 쓰기 빈도 높음.
- **B. 버퍼 단위 수집 (예: 4KB 청크)** — 청크 단위로 읽어 일괄 INSERT. DB 부하 절감, SSE 약간의 지연.
- **C. 완료 후 일괄 수집** — 프로세스 종료 후 전체 stdout/stderr를 한 번에 저장. SSE 실시간성 없음, 구현 가장 단순.

[Answer]: B

---

### Q3. [보안 패턴] Shell 제어문자 차단 레벨

NFR 요구사항 1.4에서 "쉘 제어 특수기호 포함 시 강제 차단"을 명시했습니다.  
차단 대상 문자의 범위를 결정해야 합니다.

**선택지:**

- **A. 좁은 범위** — `; | & $ \` > < \n \r \0` 등 핵심 위험 문자만 차단.
- **B. 넓은 범위** — 위 문자 외에 `( ) { } [ ] # ~ !` 등 추가 제어 문자까지 포함하여 차단.
- **C. 허용 목록(Allowlist) 방식** — 특정 허용 패턴(정규식)에 매칭되는 인자만 통과시키고, 나머지 전부 차단.

[Answer]: C

---

### Q4. [신뢰성 패턴] 타임아웃 발생 시 EventLog 처리

30초 타임아웃 발생 시, 이미 수집된 부분 출력(partial output)을 EventLog에 어떻게 처리할지 결정이 필요합니다.

**선택지:**

- **A. 부분 출력 유지** — 타임아웃 발생 이전까지 저장된 EventLog 레코드는 그대로 보존. 최종 상태에 `TIMEOUT` 마커를 추가 기록.
- **B. 롤백/삭제** — 해당 실행의 EventLog를 전부 DELETE. Job 실패 기록만 남김.

[Answer]: A

---

### Q5. [확장성 패턴] Semaphore 범위 (스코프)

`asyncio.Semaphore(2)`의 스코프를 어느 레벨로 설정할지 결정이 필요합니다.

**선택지:**

- **A. 프로세스(서버) 전역 단일 Semaphore** — 모든 Job의 CLI 실행이 하나의 Semaphore를 공유. 가장 단순하며 MVP에 적합.
- **B. Job 종류(Tool 종류)별 Semaphore** — 각 Tool(e.g., OpenSCAD)별로 별도 Semaphore. 향후 멀티 툴 확장 시 세밀한 제어 가능.

[Answer]: A
