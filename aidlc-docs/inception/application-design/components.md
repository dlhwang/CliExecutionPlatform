# 컴포넌트 정의서 (Component Definitions)

본 문서는 **LLM 기반 Workspace CLI Execution Platform**의 핵심 기능 컴포넌트의 경계와 주요 역할을 기술합니다. 모든 컴포넌트는 사용자의 결정에 따라 **도메인/기능 중심 구조 (Feature-based)**에 의거하여 배치됩니다.

---

## 1. 컴포넌트 개요

시스템은 기술 스택인 **FastAPI**와 **PostgreSQL**을 기반으로 하며, 비즈니스 영역별로 독립적인 도메인 모듈로 나뉩니다.

```
+-------------------------------------------------------------------------+
|                              FastAPI Web API                            |
+-------------------------------------------------------------------------+
       |                  |                    |                  |
       v                  v                    v                  v
+--------------+   +--------------+   +-----------------+  +--------------+
|     jobs     |   |     llm      |   |     runner      |  |     sse      |
|  JobManager  |   | ActionParser |   | CLIExecution    |  |  SSEConnManager|
|              |   | SecValidator |   | Runner          |  |              |
+--------------+   +--------------+   +-----------------+  +--------------+
       |                  |                    |                  |
       +------------------+---------+----------+------------------+
                                    |
                                    v
                            +--------------+
                            |   storage    |
                            | StorageServ. |
                            +--------------+
```

---

## 2. 모듈별 컴포넌트 상세

### 2.1 `jobs` 도메인 (Job 관리)
#### JobManager
- **목적**: 사용자의 요청을 기반으로 비동기 Job을 등록하고 상태를 추적 및 관리합니다.
- **책임**:
  - 고유한 UUID 기반 Job ID 생성 및 데이터베이스 테이블 레코드 삽입.
  - Job 상태 전이 제어 (`CREATED` -> `RUNNING` -> `COMPLETED` / `FAILED`).
  - Job의 에러 메시지 및 최종 메타데이터 갱신.
- **인터페이스 유형**: DB Repository & Service

---

### 2.2 `llm` 도메인 (LLM 계획 및 보안 검증)
#### ActionPlanParser
- **목적**: LLM이 반환하는 JSON 형태의 Action Plan을 플랫폼 내 구조체(Pydantic)로 파싱합니다.
- **책임**:
  - LLM의 텍스트 응답에서 JSON 코드 블록 추출 및 스키마 유효성 검사.
  - Action Plan 구조체 배열(`List[Action]`) 생성.

#### SecurityPolicyValidator
- **목적**: 파싱된 Action Plan이 플랫폼의 보안 제약사항을 준수하는지 물리적으로 검증합니다.
- **책임**:
  - 모든 `WRITE_FILE`, `CREATE_DIRECTORY`, `CREATE_ARTIFACT`의 대상 파일 상대 경로에 `../`이 포함되어 있거나 absolute path, 심볼릭 링크 형태인지를 차단.
  - `RUN_TOOL` 액션 시 실행하려는 실행 파일명이 화이트리스트(`openscad`)에 포함되는지 확인.
  - Command Parameter로 전달되는 arguments가 허용된 규칙 내에 있는지 쉘 인젝션 위험성을 검사.

---

### 2.3 `runner` 도메인 (격리 프로세스 실행)
#### CLIExecutionRunner
- **목적**: 격리 환경 제약을 보장하며 로컬 프로세스 상에서 외부 CLI 도구(OpenSCAD 등)를 실행합니다.
- **책임**:
  - Python `subprocess.Popen`을 활용하여 쉘 확장 없이 CLI 명령어 실행.
  - 프로세스에 최대 30초의 `timeout`을 강제하여 무한 루프 렌더링 중지 및 OS 프로세스 강제 종료(Kill).
  - CPU 및 메모리 사용량 한도를 초과하지 않도록 OS 리소스 제약(예: ulimit 또는 platform-specific limits) 감시 및 통제.
  - CLI 프로세스의 stdout/stderr 표준 출력을 읽어 실시간으로 이벤트 스토어에 전달.

---

### 2.4 `sse` 도메인 (이벤트 스트리밍 및 복구)
#### SSEConnectionManager
- **목적**: SSE 클라이언트와의 지속 연결을 수립하고 실시간 진행 로그를 안전하게 스트리밍합니다.
- **책임**:
  - 특정 Job ID에 매핑된 클라이언트 SSE 연결 리스너 관리.
  - 클라이언트가 `Last-Event-ID`를 전달하며 재연결 시, PostgreSQL DB의 `event_logs` 테이블로부터 해당 ID 이후의 누적 로그를 SQL로 정렬 조회하여 재송신(Catch-up).
  - 비동기 SQL Polling 스레드를 구동하여, Job 실행 중 발생하는 DB 이벤트 로그를 0.5초 간격으로 스캔하여 실시간 스트리밍 제공.

---

### 2.5 `storage` 도메인 (아티팩트 및 작업 공간 영속성)
#### StorageService (Interface)
- **목적**: Job 전용 Workspace 내의 파일 영속화와 다운로드를 위한 인터페이스를 정의합니다.
- **책임**:
  - Job Workspace 디렉토리 초기화 및 정리(`clean_workspace`).
  - LLM이 요청한 파일 쓰기 작업 수행.
  - 최종 3D 렌더링 아티팩트(`preview.png`, `output.stl`)를 영구 저장소에 복사 및 보관.
  - 안전한 파일 스트림 제공 (경로 Traversal 방지 경로 확인 강제).

#### LocalStorageService (Implementation)
- **목적**: 호스트 파일 시스템을 활용해 `StorageService`를 실제로 구현하는 MVP 저장소 엔진입니다.
