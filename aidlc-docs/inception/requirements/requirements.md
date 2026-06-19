# 제품 요구사항 명세서 (Requirements Specification)

본 문서는 **LLM 기반 Workspace CLI Execution Platform**의 MVP 단계 요구사항을 정의합니다.

---

## 1. Intent Analysis Summary (의도 분석 요약)

- **User Request (사용자 요청)**: 사용자가 자연어로 결과물(예: OpenSCAD 설계)을 요청하면, 서버가 Job을 생성하고 LLM이 제한된 JSON 액션 플랜을 수립하여 제한된 workspace 안에서 파일을 생성 및 OpenSCAD CLI를 격리 실행하고, 그 과정과 로그를 SSE로 실시간 전송 및 최종 산출물을 제공하는 플랫폼 구축.
- **Request Type (요청 유형)**: 신규 프로젝트 개발 (Greenfield - New Project)
- **Scope Estimate (범위 추정)**: 시스템 전반 (System-wide)
- **Complexity Estimate (복잡도 추정)**: 복잡 (FastAPI API 설계, 격리 실행 제약, DB 폴링 기반 Event Store, 실시간 SSE 스트리밍 및 Last-Event-ID 누락 복구)

---

## 2. Functional Requirements (기능 요구사항)

### Requirement R-1: Job 생성 및 전용 Workspace 관리

#### Description
사용자가 자연어로 설계 작업을 요청하면 시스템은 고유한 `Job ID`를 생성하고, 데이터베이스에 Job 상태(CREATED, RUNNING, COMPLETED, FAILED 등)를 기록한다. 또한, 호스트 파일 시스템 내에 해당 Job 전용의 격리된 디렉토리(Workspace)를 생성한다.

#### Acceptance Criteria
- 모든 파일 생성 및 CLI 실행 작업은 이 전용 Workspace 디렉토리 안에서만 이루어져야 한다.
- Workspace 경로는 외부 노출 시 절대경로가 아닌 Job ID 또는 상대적 토큰으로 식별되어야 한다.
- Job 상태 전이는 DB에 실시간으로 업데이트되어야 한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration
- **Required Test Evidence**: `test_job_lifecycle.py`에서 Job 생성 시 고유한 디렉토리가 `jobs/{job_id}` 형식으로 생성되는지 검증하고, 작업 종료 시 Clean-up 처리가 동작하는지 확인한다.

---

### Requirement R-2: LLM JSON Action Plan 생성 및 검증 (Parser/Validator)

#### Description
서버는 사용자의 자연어 프롬프트를 LLM에 전달하여 작업 계획을 수립한다. LLM은 직접 쉘 명령을 실행하는 대신, 정의된 JSON Schema에 따른 Action Plan만을 생성해야 한다. 서버는 이 Plan을 실행하기 전 철저히 검증한다.

#### Acceptance Criteria
- 허용된 Action 목록: `CREATE_DIRECTORY`, `WRITE_FILE`, `RUN_TOOL`, `CREATE_ARTIFACT`
- 모든 파일 경로 인자는 상대 경로만 허용하며, `../`, 절대 경로, 심볼릭 링크를 포함하거나 시스템 경로에 접근하려는 시도는 무조건 차단(예외 발생 및 Job 즉시 실패 처리)해야 한다.
- `RUN_TOOL` 액션에서 실행 가능한 도구는 MVP 기준 `openscad`로 한정한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit
- **Required Test Evidence**: `test_action_validator.py`에서 `../etc/passwd`나 `/usr/bin` 같은 허용되지 않은 경로가 포함된 JSON Plan을 검증할 시 `ValidationError`가 발생함을 검증한다. 또한 허용되지 않은 액션 타입 입력 시 거절되는지 검증한다.

---

### Requirement R-3: OpenSCAD CLI 격리 실행 (로컬 프로세스 격리)

#### Description
서버는 `RUN_TOOL` 액션을 실행할 때, 호스트 시스템에서 OpenSCAD CLI를 호출하되 OS 수준의 리소스 제한 및 격리를 적용한다.

#### Acceptance Criteria
- **Timeout 제약**: CLI 프로세스 실행 시간이 설정치(예: 30초)를 초과하면 프로세스를 강제 종료(Kill)하고 Job을 FAILED 상태로 전이한다.
- **리소스 제약**: CPU 사용율 및 메모리 한도를 초과할 경우 프로세스가 중단되도록 조치한다. (OS 프로세스 제한 유틸리티 활용)
- **출력 크기 제약**: 생성되는 출력 파일(preview.png, output.stl)의 최대 크기를 제한하여 디스크 풀(Full) 장애를 예방한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration/performance
- **Required Test Evidence**: `test_openscad_execution.py`에서 강제로 무한 루프가 포함된 SCAD 스크립트를 실행시켜 30초 내에 타임아웃 종료되고 리소스가 회수되는지 확인한다.

---

### Requirement R-4: SSE 실시간 스트리밍 및 Last-Event-ID 기반 복구

#### Description
사용자는 Job 진행 상태와 OpenSCAD CLI 실행 로그를 실시간으로 받아볼 수 있어야 한다. 이를 위해 Server-Sent Events (SSE)를 제공하며, 전달되는 모든 이벤트는 데이터베이스에 순차적으로 로깅된다.

#### Acceptance Criteria
- 이벤트 스키마에는 `id` (순차적 ID), `event` (이벤트 타입), `data` (메시지 본문)가 포함되어야 한다.
- 네트워크 단절 후 클라이언트가 `Last-Event-ID` 헤더를 포함하여 SSE 연결을 재시도하면, 서버는 데이터베이스의 이벤트 로그 테이블에서 해당 ID 이후의 이벤트들을 조회하여 누락 없이 재송신해야 한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: integration
- **Required Test Evidence**: `test_sse_recovery.py`에서 SSE 연결 중 임의로 클라이언트 접속을 종료하고, 몇 개의 이벤트를 백그라운드에서 발생시킨 뒤, `Last-Event-ID`를 헤더에 싣고 재요청했을 때 누락된 이벤트만 필터링되어 스트리밍에 실리는지 확인한다.

---

### Requirement R-5: Artifact Storage 추상화 및 제공

#### Description
OpenSCAD CLI 실행 결과물인 `preview.png` 또는 `output.stl` 파일, 그리고 설계 코드인 `model.scad`, `design-spec.md` 등을 최종 Artifact로 정의한다. 이들을 영구 저장하고 다운로드할 수 있는 Storage 인터페이스를 설계한다.

#### Acceptance Criteria
- 추후 S3 등 클라우드 스토리지로의 전환이 용이하도록 `StorageService` 추상 인터페이스를 작성하고, MVP 환경용으로 `LocalStorageService`를 구현한다.
- 사용자는 제공된 고유 다운로드 URL을 통해 최종 산출물을 내려받을 수 있어야 한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**: `test_storage_service.py`에서 파일 저장, 조회 및 다운로드 API 호출 시 올바른 파일 바이너리가 반환되는지 테스트한다.

---

## 3. Non-Functional Requirements (비기능 요구사항)

### NFR-1: 보안 및 입력 안전성
- **경로 검증 강제**: 사용자 입력값이나 LLM의 결과물에 의한 디렉토리 traversal 공격을 원천적으로 막기 위해, 모든 파일 I/O는 `Path.resolve()` 등을 통해 호스트 Workspace 루트의 하위 경로에 위치하는지 물리적으로 검증한다.
- **명령어 인젝션 방지**: CLI 도구 실행 시 쉘 문자열을 직접 구성하여 실행하지 않고, arguments를 리스트 형식(`subprocess.run(["openscad", ...])`)으로 구성하여 Command Injection 가능성을 차단한다.

### NFR-2: 안정성 및 복구력
- **상태 영속화**: 실시간 SSE 스트림은 메모리에만 머무르지 않고, PostgreSQL의 `event_logs` 테이블에 영속화되어 시스템 재시작 시에도 로그 이력을 복구할 수 있어야 한다.
- **비동기 처리**: 작업 실행은 FastAPI 백그라운드 태스크(BackgroundTasks) 혹은 간단한 비동기 작업 큐를 활용하여 API 응답이 블로킹되지 않도록 한다.

### NFR-3: 확장성 및 유연성
- **YAGNI 원칙 준수**: 복잡한 분산 아키텍처(Celery, Redis Stream, AWS S3 등)를 초기에 성급하게 도입하지 않고, 단일 서버 내에서 해결할 수 있는 데이터베이스 폴링과 로컬 파일 시스템을 활용한다. 대신, 각 모듈(Storage, CLI Runner 등)은 인터페이스 기반으로 설계하여 확장성을 열어둔다.

---

## 4. 추가/수정 요구사항 (Hotfix Requirements)

### Requirement R-8: 로컬 데이터베이스 타임존 설정 (KST)

#### Description
데이터베이스에 저장 및 표시되는 모든 시간 정보(Job 생성 시각, 로그 시각 등)를 한국 표준시(KST, UTC+9)로 처리하도록 데이터베이스 세션 타임존을 설정한다.

#### Acceptance Criteria
- PostgreSQL 데이터베이스 접속 시 세션 타임존을 `Asia/Seoul`로 설정하여 `func.now()` 실행 시 KST 시각이 저장되고 조회되도록 한다.
- SQLite 등 타임존 옵션을 지원하지 않는 테스트 환경 데이터베이스 URL 접속 시에는 에러가 발생하지 않도록 동적으로 구별하여 적용한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**: `tests/test_unit_1.py` 등 데이터베이스 시간 저장 관련 기능이 기존 SQLite 테스트 환경에서 통과하고, PostgreSQL 연동 시 KST 세션 타임존 파라미터가 안전하게 설정되는지 검증한다.

---

### Requirement R-9: OpenAI 호환 Chat Completions API 페이로드 지원

#### Description
HttpLLMClient가 custom endpoint 형식뿐 아니라 `https://api.openai.com/v1/chat/completions`와 같은 OpenAI 호환 Chat Completions API 규격도 자동으로 인식하여 호출하고 응답을 파싱할 수 있도록 개선한다.

#### Acceptance Criteria
- `LLM_ENDPOINT`에 `chat/completions`가 포함된 경우, 기존의 custom payload 형식이 아닌 `messages` (system, user) 배열 형식의 OpenAI Chat Completion 페이로드로 변환하여 요청을 전송한다.
- OpenAI API 응답 형식(`choices[0].message.content`)을 올바르게 파싱하여 plan 문자열을 추출하고, 그 외의 경우에는 기존 top-level `content` 키에서 추출하는 하위 호환성을 유지한다.
- 모든 API 응답 본문은 기존 비기능 요건(NFR-5-4, 5MB 초과 제한)을 엄격히 준수한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit
- **Required Test Evidence**: `tests/test_unit_5.py`에 OpenAI 형식 모의 테스트를 추가하여, OpenAI Chat Completions endpoint 호출 시 올바른 페이로드 전송 및 응답 파싱이 완료되는지 검증한다.

