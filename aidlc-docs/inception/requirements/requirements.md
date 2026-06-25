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

---

### Requirement R-10: LLM Plan Schema 시스템 프롬프트 명세화 및 오케스트레이션 에러 상세 기록

#### Description
LLM이 작업 계획을 수립할 때 DTO 스키마에 어긋나는 구조(예: RUN_TOOL 액션의 `tool_name` 대신 `tool` 필드 사용 등)를 생성하는 문제를 차단하기 위해, 시스템 프롬프트에 각 액션(CREATE_DIRECTORY, WRITE_FILE, RUN_TOOL, CREATE_ARTIFACT)의 엄격한 JSON 구조 및 허용되는 도구명(`openscad`)에 대한 가이드라인을 포함하도록 개선한다. 또한, 오케스트레이션 수행 중 예외 발생 시 예외명뿐 아니라 상세 예외 메시지(`str(exc)`)를 EventLog에 함께 저장하도록 하여 문제 추적을 쉽게 한다.

#### Acceptance Criteria
- `llm/client.py`에서 생성하는 시스템 프롬프트에 `CREATE_DIRECTORY`, `WRITE_FILE`, `RUN_TOOL`, `CREATE_ARTIFACT` 액션들의 정확한 JSON 예시와 필드명(`tool_name`, `args` 등)을 기재하여 LLM이 Pydantic DTO 형식에 완벽히 호환되게 한다.
- 시스템 프롬프트 상에서 `RUN_TOOL`의 `tool_name`은 오직 `openscad`만 허용됨을 명시한다.
- `orchestrator/service.py`에서 예외가 발생하여 `ORCHESTRATION_FAILED` 상태로 전이될 때, 상세 에러 메시지(예: `Orchestration failed: LLMPlanValidationError. Detail: Pydantic validation failed: ...`)를 로그 및 이벤트로 적재한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**: 신규 작성된 시스템 프롬프트가 `llm/client.py`에 잘 주입되는지 확인하고, 예외 발생 시 상세 에러 메시지가 EventLog 테이블 및 API Response에 정상 전달되는지 `tests/test_unit_5.py` 또는 `tests/test_unit_1.py` 등에서 모의 예외 발생을 통해 검증한다.

---

### Requirement R-12: 환경 파일 ASCII 호환성 정책

#### Description
SlowAPI와 Starlette가 `.env`를 Windows 시스템 기본 인코딩(CP949)으로 직접 읽는 현재 동작을 고려하여, 환경 파일 템플릿의 주석과 예시 값을 ASCII 문자로만 제공한다. 사용자가 템플릿을 복사해 생성하는 실제 `.env`도 ASCII-only 규칙을 따르도록 문서로 안내한다.

#### Acceptance Criteria
- `.env.sample`의 전체 내용은 ASCII 문자로만 구성한다.
- `.env.sample`의 설명 주석은 영문으로 제공한다.
- README에 Windows/SlowAPI 호환성을 위해 실제 `.env`의 주석과 값을 ASCII 문자로 유지해야 한다는 주의사항을 한국어로 명시한다.
- `database.py`, `limiter.py` 및 런타임 의존성은 변경하지 않는다.
- 현재 `.env.sample`과 이후 변경에서 비ASCII 문자가 다시 도입되지 않도록 자동화 검증을 제공한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/static validation
- **Required Test Evidence**: 신규 테스트가 `.env.sample`의 원시 바이트를 ASCII로 디코딩할 수 있는지 검증하고, 전체 회귀 테스트가 통과해야 한다.

---

### Requirement R-13: Linux 실행 환경 표준화, Docker 배포 및 서버 오류 로깅

#### Intent Analysis Summary
- **User Request**: MVP의 CLI 실행 환경을 Linux로 제한하고, Windows 로컬 개발은 WSL2를 필수로 하며, OpenSCAD를 포함한 Docker 이미지로 배포한다. 데이터베이스는 컨테이너에 포함하지 않고 기존 연결 정보로 접속한다. 백그라운드 오류는 서버 로그에서도 확인할 수 있게 한다.
- **Request Type**: Runtime Constraint Change / Infrastructure Enhancement / Bug Fix
- **Scope Estimate**: CLI Runner, Iterative Refinement Orchestrator, 로컬 개발 문서 및 컨테이너 배포 구성
- **Complexity Estimate**: 보통 - 지원 플랫폼을 축소하는 대신 Linux/WSL2 실행 계약, Docker 이미지, 외부 DB 연결, workspace 경로 및 오류 관측성을 함께 검증해야 한다.

#### Description
MVP 서버의 공식 실행 환경을 Linux로 제한한다. Windows 호스트에서 로컬 개발할 때는 WSL2의 Linux 환경에서 서버를 실행하고, 네이티브 Windows Python 실행은 지원하지 않는다. 배포 시에는 애플리케이션과 OpenSCAD CLI를 포함한 Linux Docker 이미지를 사용한다. 데이터베이스 서버는 이미지나 기본 실행 구성에 포함하지 않고 환경 변수로 전달된 기존 연결 정보에 접속한다. CLI 상대경로는 해당 Job workspace를 기준으로 해석하며, 백그라운드 오케스트레이션 예외는 EventLog와 서버 로그 모두에 기록한다.

#### Acceptance Criteria
- 공식 지원 서버 환경은 Linux이며 Windows 로컬 개발 절차는 WSL2 기반으로만 문서화한다.
- 네이티브 Windows Python 및 Windows OpenSCAD 경로는 MVP 지원 범위에서 명시적으로 제외한다.
- Linux Docker 이미지는 애플리케이션 Python 의존성과 OpenSCAD CLI를 포함하고, `docker-compose.yml`로 FastAPI 서버를 실행한다.
- `docker-compose.yml`에는 애플리케이션 서비스만 정의하고 PostgreSQL 등 DB 서비스는 추가하지 않는다.
- Docker 이미지는 DB 서버를 포함하지 않으며 `DATABASE_URL` 등 기존 연결 정보를 런타임 환경 변수 또는 env 파일로 주입받아 외부 DB에 연결한다.
- 비밀 연결 정보와 API 키는 Docker 이미지 레이어에 포함하거나 Dockerfile에 하드코딩하지 않는다.
- Job workspace와 artifact 저장 경로는 컨테이너 재생성 시에도 보존할 수 있도록 외부 volume으로 연결 가능한 경로를 사용한다.
- Linux/WSL2/Docker의 CLI 실행은 HTTP 요청 event loop를 장시간 블로킹하지 않으며 기존 timeout, 프로세스 종료, 출력 수집, 동시성 제한 동작을 유지한다.
- OpenSCAD 프로세스의 working directory는 `.workspaces/jobs/{job_id}`로 설정되고, LLM action의 상대경로가 해당 디렉터리를 기준으로 해석된다.
- 오케스트레이션 실패 시 서버 로그에 `job_id`, 예외 타입, 예외 메시지 및 traceback이 `ERROR` 수준으로 기록된다.
- EventLog의 `ORCHESTRATION_FAILED` 메시지는 기존 API/SSE 계약을 유지하되, 메시지가 비어 있는 예외도 진단 가능한 문맥을 제공한다.
- 로그에 LLM API 키, SSE 토큰 등 비밀 값이나 전체 환경 변수를 기록하지 않는다.
- WSL2 직접 실행과 Docker 실행 모두에서 유효한 action plan을 제공하면 `POST /api/v1/jobs`로 생성한 Job이 OpenSCAD CLI 단계를 통과해 산출물을 생성할 수 있다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration/container smoke
- **Required Test Evidence**:
  - `tests/test_unit_3.py`: subprocess 실행 `cwd`가 Job workspace의 절대경로인지 검증한다.
  - `tests/test_unit_5.py`: 오케스트레이션 예외 발생 시 `caplog`에서 `ERROR` 로그, `job_id`, 예외 타입 및 traceback을 확인한다.
  - `docker compose build`가 성공하고 이미지 내부에서 OpenSCAD 버전 명령 및 FastAPI 애플리케이션 import가 성공하는지 확인한다.
  - 컨테이너에 외부 `DATABASE_URL`과 workspace volume을 주입할 수 있고, 연결 정보가 이미지에 포함되지 않았는지 정적 검증한다.
  - 전체 회귀 테스트를 실행하고 WSL2 또는 Docker에서 실제 CLI smoke test로 `.scad` 입력에서 `.stl` 또는 `.png` 산출물 생성을 확인한다.

---

### Requirement R-14: Docker 컨테이너 환경에서 하위 디렉토리를 포함한 CLI 실행 결과 파일 복사 및 격리 실행 호환성

#### Description
- /tmp 임시 디렉토리에서 OpenSCAD CLI를 격리 실행한 후 생성된 결과 파일만 workspace로 복사하여 제공하는 기존 구조(R-13)에서, 출력 파일이 하위 디렉토리(예: `dice_design/octahedron_dice.stl`)를 포함하는 경우, /tmp 하위에 해당 디렉토리 구조가 존재하지 않아 OpenSCAD CLI 실행이 실패하는 현상을 해결한다.
- 또한, CLI 실행 완료 후 임시 디렉토리에서 새로 생성된 결과 파일 및 디렉토리 구조를 workspace로 복사할 때 하위 디렉토리 구조가 그대로 보존되어 복사되어야 한다.

#### Acceptance Criteria
- **디렉토리 구조 사전 생성**: OpenSCAD 실행 전에 workspace 내에 존재하는 모든 하위 디렉토리 구조를 임시 디렉토리(/tmp) 하위에 동일하게 미리 생성한다.
- **입력 파일 복사 및 상대경로 유지**: workspace 직속 및 하위 디렉토리 내에 있는 모든 `.scad` 소스 파일들을 상대 경로 구조를 그대로 유지하여 `/tmp` 하위의 동일한 경로로 복사한다.
- **출력 부모 디렉토리 자동 생성 (-o 한정)**: `args` 중 실제 사용 중인 `-o` 출력 옵션을 파싱하여, 그 뒤에 지정된 출력 경로의 부모 디렉토리를 `/tmp` 내부에 사전에 생성(`mkdir -p`)한다. (기타 확인되지 않은 옵션 파싱은 배제)
- **경로 무결성 검증**: 모든 파일 복사 및 디렉토리 생성 경로는 resolve 후 base directory(workspace) 하위에 위치하는지 물리적으로 검증하여 Path Traversal 우회를 원천 차단한다.
- **파일 기준 Snapshot 비교 기반 복사**: CLI 실행 전 임시 디렉토리 내의 파일 목록 및 정보(크기, 수정 시간 등)를 **파일 기준으로만 스냅샷**을 찍어 관리한다. 실행 후 스냅샷과 비교하여 새로 생성되었거나 크기/수정 시간이 변경된 파일만 선별한다.
- **기존 파일 충돌 차단 정책**: workspace로의 결과 반영 시, `-o`로 명시된 출력 파일은 덮어쓰기를 명시적으로 허용하되, 그 외 기존 파일(입력 소스 파일 등)을 덮어쓰는 동작은 엄격히 차단한다.
- **기존 방어 메커니즘 유지**: 기존의 timeout(30초), resource limit, Path Traversal 방어 로직은 손상 없이 완벽히 유지한다.

#### Verification Expectations
- **Expected Test Level**: unit/integration
- **Required Test Evidence**:
  - `tests/test_unit_3.py` 내 장애 재현 통합 테스트: args로 `["-o", "dice_design/octahedron_dice.stl", "dice_design/octahedron_dice.scad"]`를 전달했을 때, 오류 없이 성공하고 workspace 내부 해당 하위 경로에 최종 stl 파일이 정상 생성되는지 검증한다.
  - `tests/test_unit_3.py` 내 방어 테스트: `../escape.stl` 등 Path Traversal 위험이 있는 출력 경로나 절대 경로 출력을 args로 주는 시나리오가 올바르게 차단 및 예외 처리되는지 검증한다.
  - 기존 timeout, 리소스 제한, Path Traversal 등 기존 58개 전체 테스트 스위트의 회귀 없음 증명.

### Requirement R-15: OpenSCAD 코드 생성 제약 조건 강화 및 SCAD 정적 검증기 추가

#### Intent Analysis Summary
- **User Request**: LLM에게 OpenSCAD 코드를 만들라고 할 때, Markdown 코드 펜스 미사용, vector 인덱스 접근(`v[0]`), 더블 쿼트 사용, degrees 삼각함수 처리 등 엄격한 제약을 프롬프트에 주입한다. 또한 scad 생성/수정 완료 시, 실행 전에 구문 오류를 검증하여 위반 시 `LLMPlanValidationError`를 발생시켜 refinement 루프를 타게 한다.
- **Request Type**: Enhancement / Validation
- **Scope Estimate**: `llm/client.py` (시스템 프롬프트), `llm/validator.py` (또는 `llm/dependency_validator.py` 등 validator 모듈), `orchestrator/actions.py` (또는 `llm/service.py`)
- **Complexity Estimate**: 보통 - 정규식 또는 정적 텍스트 검색을 활용하여 SCAD 파일의 문법적 오류를 가려내고 이를 Action Plan Validation 단계에서 필터링하는 정적 검증 논리를 설계해야 한다.

#### Description
LLM이 생성한 OpenSCAD 코드의 구문 오류(예: `v.x` 형태의 벡터 멤버 속성 접근, 싱글 쿼트 사용, 라디안 변환을 위한 삼각함수 `180 / PI` 연산 등)가 CLI 컴파일 에러를 일으키는 문제를 예방한다. 이를 위해, LLM 시스템 프롬프트에 구체적인 OpenSCAD 코드 생성 규칙을 강제하도록 시스템 프롬프트를 보강하고, Action Plan Validation 단계에서 생성/수정될 scad 파일의 내용을 정적으로 검증(Lightweight Static Validation)하는 스키마/검사 규칙을 구현한다. 검증에 실패할 경우 `LLMPlanValidationError`를 발생시켜 오케스트레이션 엔진이 이를 감지하고 에러 메시지를 피드백으로 전달하여 자동 Refinement Loop(최대 2회)를 수행하도록 유도한다.

#### Acceptance Criteria
- **LLM 프롬프트 제약 조건 주입**: `llm/client.py`의 시스템 프롬프트에 다음 생성 규칙을 명시적으로 강제한다.
  - Markdown 코드 펜스(fences) 사용 금지
  - 설명글, prose, OpenSCAD 문법 이외의 불필요한 주석(explanations) 제거
  - 벡터 접근 시 반드시 인덱스 구문(`v[0]`, `v[1]`, `v[2]`) 사용 강제, 속성 접근(`.x`, `.y`, `.z`) 절대 금지
  - 문자열 지정 시 반드시 더블 쿼트(`"`) 사용 강제, 싱글 쿼트(`'`) 절대 금지
  - OpenSCAD 삼각함수(`cos`, `sin`, `atan2` 등)는 degree 단위이므로 `180 / PI` 또는 `PI / 180` 등 라디안 변환 수식 사용 금지
- **SCAD 정적 검증기 구현 (Lightweight Static Validation)**:
  - LLM Action Plan 검증 시점(`llm/service.py` 또는 `llm/validator.py`)에서 `WRITE_FILE` 액션을 통해 `.scad` 확장자 파일이 작성되거나 수정될 경우, 파일 쓰기 실행 전에 파일 내용을 정적으로 정밀 검사한다.
  - 검사 규칙:
    1. 파일 내에 `.x`, `.y`, `.z` 형태의 속성 접근(예: `vector.x`, `point.y` 등 정규식 패턴 `\w+\.[xyz]\b`)이 발견되면 즉시 차단한다. (주석 내의 텍스트가 아닌 실제 실행 구문 중심 검출)
    2. 파일 내에 싱글 쿼트 `'`가 포함된 문자열/문자 표현이 존재하면 차단한다.
    3. 파일 내에 `180\s*/\s*PI` 또는 `PI\s*/\s*180` 수식이 포함되어 있다면 차단한다.
    4. 파일 내에 Markdown 코드 펜스(예: ` ```scad `, ` ``` ` 등)가 포함되어 있다면 차단한다.
    5. 파일 첫 부분이나 중간에 설명문/prose(예: `Here is`, `The following`, `아래는`, `다음은` 등)로 시작하거나 삽입되어 있으면 차단한다.
    6. 파일 크기가 0바이트인 빈 SCAD 파일인 경우 차단한다.
    7. 파일 전체 내용 중 OpenSCAD 기본 키워드(`module`, `polyhedron`, `cube`, `sphere`, `cylinder`, `difference`, `union`, `intersection` 등) 중 단 하나도 발견되지 않는 경우 최소 OpenSCAD 구조 검증 실패로 판단하여 차단한다.
- **예외 전이 및 Refinement 연동**:
  - scad 정적 검증에 실패할 경우 `LLMPlanValidationError`를 발생시킨다.
  - 오케스트레이터(`orchestrator/service.py`)는 이 에러를 받아 LLM에게 "OpenSCAD 구문 위반 사항"을 구체적인 피드백 메시지로 구성해 전달하고 Refinement를 유도한다.
- **기존 비기능 및 보안 요건 유지**:
  - 기존의 모든 보안/비기능 요건과 58개 테스트 회귀 방지가 완벽히 보장되어야 한다.

#### Runtime Refinement 보완 요구사항

- OpenSCAD가 비정상 종료하면 `CLIExecutionError`가 exit code와 함께 stdout 및 stderr의 bounded tail을 보유해야 한다. 전체 출력, action plan JSON, SCAD 전체 본문, traceback은 LLM 피드백에 포함하지 않는다.
- `Current top level object is empty.`를 `[SCAD_EMPTY_TOP_LEVEL]` 진단으로 감지한다.
- `Ignoring 3D child object for 2D operation`을 `[SCAD_2D_3D_MIXED_OPERATION]` 진단으로 감지한다.
- 위 진단과 짧은 대표 출력만 현재 LLM 재시도 요청의 `retry_feedback`으로 전달한다. 과거 시도의 피드백은 누적하지 않는다.
- 런타임 진단은 OpenSCAD의 실제 출력 문자열을 우선 신뢰한다. `ScadStaticValidator`의 2D/3D 혼용 휴리스틱은 오탐 없이 검증 가능한 최소 패턴이 확인되는 경우에만 추가하고, 그렇지 않으면 N/A 사유를 테스트·구현 요약에 기록한다.
- 런타임 재시도는 기존 최대 2회 정책을 유지하며, 최종 성공한 action plan만 저장하고 Job을 `COMPLETED`로 전이한다.

#### R-15A 추가 계약

- 정적 검증은 원본 line number를 보존하는 comment-masked code를 분석한다.
- vector property access와 radian conversion 같은 syntax-like 규칙은 comment 및 double-quoted string literal 내부 패턴을 무시한다.
- feedback에는 bounded rule summary와 대표 원본 line snippet만 포함하며 전체 SCAD content를 포함하지 않는다.

#### R-15B 추가 계약

- diagnostics는 bounded stdout/stderr tail만 입력으로 사용한다.
- 전체 process output, SCAD content, action plan JSON, traceback은 `CLIExecutionError.__str__`와 diagnostics feedback에 포함하지 않는다.
- stdout/stderr는 concurrently drain하며, 각 emitted line은 기존 `CLI_OUTPUT` EventLog로 저장하고 스트림별 bounded tail만 예외와 diagnostics용으로 보존한다.

#### R-15C 추가 계약

1. `generate_actions`는 parse → validation → execution refinement의 단일 소유자다.
2. `execution_cb`는 validation 후 final actions 반환 전에 실행한다.
3. runtime failure는 R-15B bounded diagnostics feedback으로 변환한다.
4. feedback은 현재 attempt failure만 포함하고 과거 feedback을 누적하지 않는다.
5. 성공적으로 실행된 attempt의 actions만 반환·저장한다.
6. 각 attempt는 isolated workspace 또는 테스트된 동등 rollback/overwrite 정책을 사용한다.
7. failed attempt artifact는 final job artifact로 승격하지 않는다.
8. non-idempotent external side effect는 runtime refinement retry boundary 밖에 둔다.
9. final plan 저장과 실행 성공 후에만 Job을 `COMPLETED`로 전이한다.
10. attempt 소진 시 bounded failure reason으로 Job을 `FAILED`로 전이한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**:
  - `tests/test_unit_2.py` 또는 신규 테스트에 `test_scad_static_validation_invalid_patterns` 및 `test_scad_static_validation_valid_scad`를 추가하여 각 패턴(속성 접근, 싱글 쿼트, 라디안 연산, 빈 파일, 무관한 prose, 코드 펜스 등)이 올바르게 오동작 없이 검출되는지 검증한다.
  - `tests/test_unit_5.py`에 validation 실패 시 refinement가 트리거되어 정상적으로 llm에 오류 피드백 메시지가 전달되는지 검증하는 integration 테스트 케이스를 추가하거나 보완한다.
  - 기존 58개 전체 테스트 통과 증명.
  - `tests/test_unit_3.py`에서 stdout/stderr tail이 `CLIExecutionError`에 포함되고 크기가 제한되는지 검증한다.
  - `tests/test_unit_3.py`에서 empty top-level 및 2D/3D 혼용 메시지가 안정적인 Rule ID로 분류되는지 검증한다.
  - `tests/test_unit_5.py`에서 첫 실행 실패의 bounded 진단 피드백이 다음 LLM 요청에 전달되고, 수정된 두 번째 계획 실행 후 Job이 완료되는지 검증한다.

---

### Requirement R-16: Artifact ID 기반 보안 다운로드

#### Intent Analysis Summary
- **User Request**: 클라이언트가 서버 경로나 파일명을 전달하지 않고 `artifact_id`만 사용하여 생성 결과물을 다운로드하는 보안 API를 제공한다.
- **Request Type**: New Feature / Security Enhancement
- **Scope Estimate**: Artifact 영속 모델, 생성 시 메타데이터 등록, 서비스 계층 경로 검증, FastAPI 라우터, DB 마이그레이션 및 자동화 테스트
- **Complexity Estimate**: 보통 - API 자체는 단순하지만 DB 메타데이터와 물리 파일의 일관성, 경로 탈출·절대경로·공통 접두사 우회 방어가 필요하다.

#### Description
`GET /api/v1/artifacts/{artifact_id}/download` 엔드포인트는 DB의 Artifact 메타데이터를 `artifact_id`로 조회하고, 연결된 Job의 workspace root를 기준으로 `artifact.relative_path`를 해석하여 검증된 일반 파일만 반환한다. 클라이언트 요청에는 경로나 파일명을 입력받는 필드를 두지 않는다.

Artifact 메타데이터는 최소한 고유 `id`, 소유 `job_id`, `relative_path`, 다운로드 `filename`, `content_type`을 보유해야 하며, `CREATE_ARTIFACT` 성공 시 물리 파일 승격과 일관되게 저장되어야 한다.

#### Acceptance Criteria
- API 경로는 정확히 `GET /api/v1/artifacts/{artifact_id}/download`이며 클라이언트 입력은 `artifact_id`만 허용한다.
- 서비스는 `artifact_id`로 Artifact 메타데이터를 DB에서 조회하고, 존재하지 않으면 HTTP 404를 반환한다.
- 서비스는 Artifact의 `job_id`로 소유 Job의 workspace root를 결정한다.
- Artifact 등록 시 `relative_path`가 소유 Job workspace root 기준의 유효한 상대경로인지 서비스 계층에서 검증한다.
- Artifact 등록 시 절대경로, 빈 경로, `.`, `..`, `../` segment 또는 플랫폼별 동등 경로 segment를 포함하는 경로를 거부한다.
- Artifact 등록 시 workspace root와 후보 경로를 `Path.resolve()`로 정규화하고, 후보가 workspace root 내부인지 검증한 후에만 메타데이터를 영속화한다.
- 다운로드 시 등록 단계의 검증 결과를 신뢰 경계로 간주하지 않고, DB의 `artifact.relative_path`에 대해 `Path.resolve()` 기반 물리 경로 검증을 다시 수행한다.
- `artifact.relative_path`가 절대경로이면 파일 접근 전에 차단한다.
- workspace root와 대상 경로를 각각 `Path.resolve()`로 정규화한다.
- 정규화된 대상 경로가 정규화된 workspace root 내부인지 `Path.is_relative_to()` 또는 동등하게 경로 구성요소를 비교하는 안전한 헬퍼로 검증한다.
- `../` traversal과 workspace가 `/tmp/jobs/job1`일 때 `/tmp/jobs/job1_evil`로 탈출하는 공통 접두사 우회를 차단한다.
- 문자열 `startswith`만으로 경계 검사를 구현하지 않는다.
- 경로 탈출, 절대경로, prefix-bypass 검증 실패는 HTTP 403으로 반환한다.
- 존재하지 않는 `artifact_id`, 존재하지 않는 물리 파일, 또는 일반 파일이 아닌 대상은 HTTP 404로 반환한다.
- 성공 시 `FileResponse`에 검증된 파일 경로, `artifact.content_type`, `artifact.filename`을 전달한다.
- 성공 응답은 `Content-Type`과 `Content-Disposition`의 다운로드 `filename`을 자동화 테스트로 검증 가능한 형태로 반환한다.
- 사용자용 오류 메시지와 응답 본문에는 workspace root나 대상 파일의 절대 서버 경로를 포함하지 않는다.
- 경로 검증과 파일 검증은 라우터가 아니라 `ArtifactService` 또는 재사용 가능한 경로 보안 헬퍼에서 수행한다.
- 인증·인가 검사는 R-16 범위에서 제외하되, 추후 소유권·권한 검사를 삽입할 수 있도록 Artifact 조회와 다운로드 결정을 `ArtifactService` 내부에 유지한다.
- 기존 Job ID/파일명 기반 다운로드 API의 유지·폐기 여부와 무관하게 신규 API는 파일명 또는 경로를 신뢰 경계 밖의 입력으로 받지 않는다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration/security
- **Required Test Evidence**:
  - 유효한 DB Artifact와 workspace 일반 파일에 대해 HTTP 200, 파일 바이트, `Content-Type`, 다운로드 파일명을 검증한다.
  - Artifact 등록 시 정상 상대경로는 허용하고 절대경로, 빈 경로, `.`, `..`, `../` segment 포함 경로는 거부하는 서비스 단위 테스트를 수행한다.
  - 알 수 없는 `artifact_id`가 HTTP 404를 반환하는지 검증한다.
  - DB Artifact는 존재하지만 물리 파일이 없는 경우 HTTP 404를 반환하는지 검증한다.
  - DB 변조 또는 레거시 데이터로 `artifact.relative_path`에 주입된 `../` traversal이 다운로드 시 재검증되어 HTTP 403으로 차단되는지 검증한다.
  - 절대경로 `artifact.relative_path`가 HTTP 403으로 차단되는지 검증한다.
  - workspace와 문자열 접두사는 같지만 형제 경로인 prefix-bypass 대상이 HTTP 403으로 차단되는지 검증한다.
  - 경로가 디렉터리 등 일반 파일이 아닌 대상을 가리키면 HTTP 404를 반환하는지 검증한다.
  - 성공 응답의 `Content-Type`과 `Content-Disposition` filename을 검증한다.
  - 모든 실패 응답에 절대 서버 경로가 포함되지 않는지 검증한다.
  - 전체 기존 테스트 스위트가 회귀 없이 통과해야 한다.

---

### Requirement R-17: Job ID 기반 아티팩트 목록 조회 API

#### Intent Analysis Summary
- **User Request**: 프론트엔드에서 Job ID를 이용해 해당 Job에 속한 아티팩트(결과물)들의 목록을 조회하여 각 아티팩트의 ID와 파일명 등을 받아올 수 있는 API를 제공한다.
- **Request Type**: New Feature
- **Scope Estimate**: jobs/router.py, jobs/service.py, jobs/schemas.py, 자동화 테스트
- **Complexity Estimate**: 보통 - 조회 동작이나, Job의 완료 여부 및 존재 여부에 따른 적절한 에러 핸들링과 보안상 메타데이터 노출 제한(상대/절대 경로 제외)을 구현해야 한다.

#### Description
- `GET /api/v1/jobs/{job_id}/artifacts` 엔드포인트를 구현하여 특정 Job에 속한 모든 아티팩트들의 목록을 조회한다.
- 보안 수칙 및 정보 노출 최소화 원칙에 따라, 응답 스펙은 `id` (UUID), `filename` (String), `content_type` (String), `created_at` (DateTime) 필드만 포함하고, 내부 물리 경로를 추정할 수 있는 `relative_path` 등은 응답에서 제외한다.
- 오직 완료(`COMPLETED`) 상태인 Job에 대해서만 아티팩트 목록 조회를 허용한다.

#### Acceptance Criteria
- API 경로는 정확히 `GET /api/v1/jobs/{job_id}/artifacts`이며, HTTP Method는 `GET`이다.
- DB에서 `job_id`로 Job을 조회하여 존재하지 않는 경우 HTTP 404 Not Found 에러를 반환한다.
- Job이 존재하지만 상태가 `COMPLETED`가 아닌 경우 (예: `CREATED`, `RUNNING`, `FAILED`) HTTP 400 Bad Request 에러를 반환한다.
- 아티팩트 목록의 각 항목 스키마는 `id` (UUID), `filename` (String), `content_type` (String), `created_at` (DateTime) 필드를 가진다.
- 응답 데이터에 `relative_path` 등 서버 내부 디렉토리/경로 정보가 포함되어서는 안 된다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**:
  - `tests/test_unit_2.py` 또는 그 외 적절한 단위/통합 테스트 코드 파일에 다음 테스트 케이스를 추가하여 검증한다:
    - 성공 케이스: `COMPLETED` 상태의 Job과 해당 Job에 매핑된 아티팩트들이 DB에 존재할 때 목록이 정상적으로 반환되며, 각 아티팩트 응답에 `id`, `filename`, `content_type`, `created_at`만 포함되고 `relative_path`는 포함되지 않는지 확인한다.
    - 예외 케이스 1: DB에 존재하지 않는 `job_id`를 제공해 조회하는 경우 HTTP 404 Not Found 에러가 발생하는지 확인한다.
    - 예외 케이스 2: Job 상태가 `COMPLETED`가 아닌 경우 (예: `CREATED`, `RUNNING`, `FAILED`) 조회 시 HTTP 400 Bad Request 에러가 발생하는지 확인한다.
    - 전체 기존 테스트 스위트가 회귀 없이 통과해야 한다.

---

## 5. AI-MAKING 멀티턴 SCAD 생성 기능 요구사항 (R-18)

### Requirement R-18: AI-MAKING 워크플로우 기반 멀티턴 CAD/SCAD 생성 기능 설계

#### Intent Analysis Summary
- **User Request**: AI-MAKING 워크플로우(`D:\workspace\scad\ai-making-rules\core-workflow.md`)를 반영하여 사용자 대화 및 피드백을 수집하며 고품질 CAD/SCAD 설계도를 생성하는 멀티턴 오케스트레이션 기능 설계.
- **Request Type**: New Feature / Architectural Design
- **Scope Estimate**: JobOrchestratorService, LLM Client, Session State, API Router
- **Complexity Estimate**: 보통/높음 - 멀티턴 상태 전이 기획, 실측 데이터 및 공차 파싱, 테스트 쿠폰 피드백 반영, 토큰 절약을 위한 컨텍스트 요약/축소(Context Pruning) 로직 필요.

#### Description
사용자의 자연어 요청에 따라 실측 공차를 반영하고 단계별 승인을 거치는 고품질 설계 워크플로우를 구현하기 위해 시스템은 다음 기능을 제공해야 한다.
1. **단계별 명시적 UI 전진 및 승인 구조 (State Machine)**:
   - Inception 단계(요구사항 분석, 실측 측정, 재료 분석) 및 Execution 단계(테스트 쿠폰, 본 모델 설계)의 현재 단계를 API/SSE를 통해 투명하게 전달한다.
   - 각 단계 전환 시 사용자 승인(Approve) 또는 질문 답변을 획득해야 다음 상태로 전진하는 오케스트레이션 로직을 적용한다.
2. **실측 치수 되묻기 및 동적 공차 파싱 (Proactive Clarification)**:
   - 사용자가 처음부터 치수를 자세히 제공하지 않으므로, 요청한 조형물(예: 충전 도크, 기어, 함체)에 맞는 실측 필요 항목(Measured Specs)을 LLM이 스스로 판단하여 질문 리스트로 도출하도록 한다.
   - 사용자는 자연어로 치수와 공차를 답변할 수 있으며, 시스템은 이를 파싱하여 세션 스펙으로 유지한다.
3. **토큰 최적화를 위한 컨텍스트 축소 및 단계별 지식 분할 (Context Pruning & Specialized Knowledge Injection)**:
   - 멀티턴의 누적 대화 기록 전체와 전체 워크플로우 규칙을 매번 LLM에 전달하면 토큰 비용과 컨텍스트 한계 초과 우려가 존재한다.
   - 이를 방지하기 위해, 전체 워크플로우를 세부 단계(요구사항 분석, 실측 측정, 테스트 쿠폰 설계, 본 설계 등)로 명확히 분할하고, 각 단계 실행 시 **해당 단계에 꼭 필요한 규칙/지식(예: 해당 단계 전용 가이드라인)과 요약 정형화 상태(`making-state.json`)의 서브셋**만 동적으로 조립하여 주입한다. 이전 턴의 원문 대화 기록이나 불필요한 다른 단계의 가이드를 차단함으로써 입력 토큰량을 최소화한다.
4. **테스트 쿠폰 검증 루프 (Test Coupon Design)**:
   - 조립이나 볼트 체결 등 공차가 민감한 구간을 검증하기 위한 단순화된 형상의 테스트 조각(`test_coupon.scad`)을 선제적으로 생성하여 사용자의 물리적 조립성 피드백을 수집하고, 이를 본 모델 설계 파라미터에 피드백 루프로 자동 주입한다.

#### Acceptance Criteria
- **명시적 전이**: API를 통해 현재 Job의 세부 AI-MAKING 상태(요구사항 대기, 테스트 쿠폰 피드백 대기, 본 설계 대기 등)를 조회할 수 있어야 한다.
- **자연어 치수 획득**: 실측치가 누락된 경우 LLM이 질문을 작성하여 사용자 답변을 자연어로 유도하고 이를 `measured-specs` 컨텍스트에 바인딩한다.
- **토큰 최적화 및 지식 분할 검증**: 특정 단계(예: 본 모델 생성) 요청 시, 전체 AI-MAKING 워크플로우가 아닌 해당 본 설계 전용 규칙 파일과 누적 상태(`making-state.json`)만 컨텍스트에 포함되며, 이전 대화 원문은 제외하여 입력 토큰이 최적화됨을 검증한다.
- **테스트 쿠폰 선행**: 조립이 필요한 복잡한 제품 설계 시 본 설계 이전에 `test_coupon.scad` 생성 액션 및 사용자 검토 단계를 반드시 통과해야 한다.

#### Verification Expectations
- **Automation Required**: Yes
- **Expected Test Level**: unit/integration
- **Required Test Evidence**:
  - `tests/test_unit_aimaking.py`를 추가하여 AI-MAKING 오케스트레이터의 단계별 상태 전이(요구사항 수집 -> 테스트 쿠폰 검증 -> 본 설계 완료) 로직을 모의 테스트한다.
  - 컨텍스트 빌드 시 이전 턴의 raw 대화 텍스트가 전달되지 않고, 요약된 JSON 상태 데이터만 Prompt에 포함되는지 단언문으로 검증한다.
  - 누락된 치수 감지 프롬프트 템플릿의 정상 빌드 여부를 유닛 테스트로 검증한다.
