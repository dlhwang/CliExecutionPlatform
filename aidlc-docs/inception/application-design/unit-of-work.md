# 작업 단위 정의서 (Unit of Work Definitions)

본 문서는 **LLM 기반 Workspace CLI Execution Platform** 프로젝트의 개발 세부 유닛(Unit of Work) 정의와 Greenfield 프로젝트 코드 구조 및 패키지 관리 전략을 정의합니다.

---

## 1. 프로젝트 코드 디렉토리 구조 (Code Organization)

본 프로젝트는 도메인 중심 아키텍처 및 PIP + Virtualenv 관리 방식을 따르며, 다음과 같이 구조화됩니다. 모든 애플리케이션 코드는 `D:\workspace\CLI-Execution-Platform\`의 루트에 위치하며, `aidlc-docs/`에는 문서만 관리합니다.

```
D:\workspace\CLI-Execution-Platform\
├── venv/                      # Python 가상 환경 (로컬 격리용)
├── requirements.txt           # 의존성 패키지 목록 (fastapi, psycopg2, uvicorn 등)
├── main.py                    # FastAPI 애플리케이션 진입점 (EntryPoint)
│
├── jobs/                      # jobs 도메인 (Job 관리)
│   ├── __init__.py
│   ├── router.py              # Job 생성/조회 API 엔드포인트
│   ├── service.py             # Job 비즈니스 로직 (JobManager)
│   └── models.py              # Job DB 스키마 (SQLAlchemy)
│
├── llm/                       # llm 도메인 (Action Plan 및 검증)
│   ├── __init__.py
│   ├── parser.py              # LLM JSON Action Plan 파서 (ActionPlanParser)
│   ├── validator.py           # 경로 traversal 차단 등 보안 검증 (SecurityPolicyValidator)
│   └── schemas.py             # Pydantic Action Plan 스키마
│
├── runner/                    # runner 도메인 (CLI 실행기)
│   ├── __init__.py
│   └── executor.py            # OpenSCAD CLI 로컬 프로세스 실행기 (CLIExecutionRunner)
│
├── sse/                       # sse 도메인 (실시간 모니터링)
│   ├── __init__.py
│   └── manager.py             # SSE 연결 관리 및 SQL DB 로그 폴링 (SSEConnectionManager)
│
└── storage/                   # storage 도메인 (작업 공간 및 파일 저장)
    ├── __init__.py
    ├── interface.py           # StorageService 추상 클래스
    └── local.py               # LocalStorageService 구현 클래스
```

---

## 2. 작업 단위 (Unit of Work) 정의 및 책임

### Unit 1: API Core & Storage Service
- **목적**: 시스템의 핵심 뼈대인 API 뼈대, DB 스키마 영속화, 그리고 물리 저장소 추상 레이어를 마련합니다.
- **주요 책임**:
  - FastAPI 및 DB Connection(PostgreSQL/SQLAlchemy) 설정.
  - `Job` 및 `Event Log` 테이블 생성을 위한 데이터베이스 마이그레이션 스키마 구현.
  - `StorageService` 추상 인터페이스 및 호스트 파일 시스템을 활용한 `LocalStorageService` 구현.
  - Job 생성 POST API 및 특정 Job ID 기반 Artifact 다운로드 GET API 작성.

### Unit 2: LLM Plan Parser & Validator
- **목적**: LLM이 반환하는 액션 플랜을 파싱하고 경로 traversal 등 악성 입력을 철저히 검사하는 모듈을 완성합니다.
- **주요 책임**:
  - Pydantic을 활용한 JSON 액션 플랜 스키마 정의 (`CREATE_DIRECTORY`, `WRITE_FILE`, `RUN_TOOL`, `CREATE_ARTIFACT`).
  - LLM 마크다운 응답에서 JSON 문자열을 파싱하는 `ActionPlanParser` 작성.
  - 대상 상대경로 내 `../`, 절대 경로, 심볼릭 링크를 원천 차단하고 `Path.resolve()` 기반의 물리 영역 검증을 수행하는 `SecurityPolicyValidator` 구현.

### Unit 3: CLI Execution Runner
- **목적**: OpenSCAD CLI 렌더링 도구를 안전하게 실행하고 리소스를 엄격히 제한하는 컴포넌트를 마련합니다.
- **주요 책임**:
  - `subprocess.Popen`을 활용해 쉘 인젝션 위험 없이 인수 배열 형식으로 OpenSCAD CLI 호출.
  - 실행 후 최대 30초 한도로 프로세스를 강제 종료(Kill)하는 타임아웃 메커니즘 장착.
  - 프로세스의 실시간 stdout/stderr 스트림을 출력 라인 단위로 수집하는 핸들러 구현.

### Unit 4: SSE Streaming & Event Catch-up
- **목적**: 진행 상황과 CLI 출력 로그를 실시간 중계하고 단절 시 완벽 복구할 수 있는 파이프라인을 구축합니다.
- **주요 책임**:
  - SSE 연결 엔드포인트 `/api/v1/jobs/{job_id}/stream` 구현.
  - 0.5초 간격으로 `event_logs` 테이블을 쿼리하는 비동기 SQL Polling 리스너 구현.
  - 클라이언트가 `Last-Event-ID` 헤더를 전송하며 연결 재시도 시, 해당 ID 이후의 누락 이벤트를 DB에서 역추적하여 먼저 일괄 전송(Catch-up)하는 복구 로직 구현.

### Unit 5: Iterative Refinement Orchestrator
- **목적**: 개별 컴포넌트들을 비동기 통합 처리하고 대화형 반복 설계(피드백) 시나리오를 지원하는 오케스트레이터를 구성합니다.
- **주요 책임**:
  - `JobOrchestratorService` 구현 (FastAPI `BackgroundTasks` 상에서 구동).
  - LLM API와의 실제 요청/응답 연동 및 예외 처리(에러 시 Job을 `FAILED` 상태 처리하고 리소스 정리).
  - 이전 완료된 Job ID가 피드백 요청과 함께 올 때, 이전 Workspace 내 `model.scad` 파일을 새 작업 공간으로 복제하고 LLM의 컨텍스트로 제공하는 로직 구현.
