# LLM 기반 Workspace CLI Execution Platform (Backend MVP)

본 플랫폼은 사용자의 자연어 요청에 따라 서버 내에 안전하게 격리된 가상 작업 공간(Workspace)을 생성하고, LLM과 상호작용하여 제약된 JSON 액션 플랜을 도출·선검증한 뒤 허용된 CLI 도구를 실행하고, 그 진행 상황을 Server-Sent Events(SSE)로 실시간 스트리밍 및 유실 시 복원해 주는 고안전성 오케스트레이션 API 백엔드 플랫폼입니다.

기본 지원 도구로 **OpenSCAD CLI** 환경이 적용되어 있으며, 아티팩트 자동 생성 및 대화형 반복 수정 피드백 루프를 지원합니다.

---

## 🚀 주요 기능 및 특징

1. **UUIDv7 기반 Job 식별 및 순서 정렬**: 시간 정렬 및 인덱싱 성능이 뛰어난 UUIDv7 규격 적용.
2. **로컬 격리 가상 공간 (Storage)**: Job별 독립된 `.workspaces/{job_id}/` 디렉토리 보호 및 `../`, 절대 경로, 심볼릭 링크를 활용한 디렉토리 Traversal 공격 차단.
3. **LLM Plan Parser & Validator (이중 방어)**: 
   - LLM 응답 내 Markdown 및 Fallback JSON 계획 자동 추출.
   - 비인가 CLI 명령어(예: bash 등) 사전 차단, 샌드박스 보안 규칙을 사전에 검증하여 위반 시 `SECURITY_ALERT` DB 적재.
4. **보안 제어 CLI 실행 (Runner)**: 
   - CLI 실행 인자 내 특수문자 Command Injection 방어 (Allowlist 방식).
   - 프로세스 타임아웃 **30초** 강제 종료(SIGKILL) 및 이전까지의 partial log 보존.
   - 단일 머신 최대 동시 실행 CLI 프로세스 **2개** 제한.
5. **실시간 SSE 스트리밍 & Event Catch-up**:
   - `X-Stream-Token` 기반 1회용 스트림 접속 보안 인증.
   - `Last-Event-ID` 헤더 기반 세션 유실 이벤트 완벽 복구 (Catch-up).
   - 최대 동시 SSE 커넥션 수 **20개** 제한 및 DB 일시 장애 지수 백오프 자동 재시도.
6. **Iterative Refinement Orchestrator**:
   - 완료된 부모 Job에 기반한 수정 요청(Refinement) 시 이전 결과물(`model.scad`, `design-spec.md`) 자동 상속 (최대 5MB 용량 제한).
   - 120초 LLM 클라이언트 타임아웃 및 2회 재시도.
   - 백엔드 재기동 시 15분을 초과한 Stale 상태의 `RUNNING` Job 자동 FAILED 복구(lifespan).

---

## 🛠 기술 스택

- **Framework**: FastAPI (Python 3.13)
- **Database**: PostgreSQL (Production) / SQLite (Test in-memory)
- **ORM / Migrations**: SQLAlchemy
- **CLI Runtime**: Linux OpenSCAD CLI + Xvfb
- **Deployment**: Docker Compose V2 (single application service)
- **Testing**: pytest, slowapi (Rate Limiter), httpx

---

## 📂 디렉토리 구조

```text
CLI-Execution-Platform/
├── main.py               # FastAPI 웹 애플리케이션 진입점 (Lifespan 설정 포함)
├── database.py           # SQLAlchemy 데이터베이스 설정 및 세션 관리
├── limiter.py            # API Rate Limiter 설정 (slowapi)
├── requirements.txt      # 프로젝트 의존 라이브러리 목록
├── .env.sample           # 개발 환경 변수 설정 템플릿
├── Dockerfile            # Python/OpenSCAD Linux 애플리케이션 이미지
├── docker-compose.yml    # 앱 단일 서비스, 외부 DB 연결, workspace volume
├── .dockerignore         # 비밀정보 및 로컬 산출물 build context 제외
├── docker/
│   └── openscad-headless # Xvfb 기반 OpenSCAD 실행 adapter
│
├── jobs/                 # Job 및 EventLog 도메인 패키지
│   ├── models.py         # DB ORM 모델 (UUIDv7 및 parent_job_id 계보 구현)
│   ├── schemas.py        # Pydantic DTO (Job 생성/Refine 요청 스키마)
│   ├── service.py        # Job 비즈니스 로직 처리 서비스
│   └── router.py         # HTTP API 라우터 (Job 생성, Refine, 아티팩트 다운로드)
│
├── storage/              # Workspace 및 파일 스토리지 모듈
│   ├── interface.py      # StorageService 추상 계약 인터페이스
│   └── local.py          # Traversal 방어 기능 탑재 로컬 파일 스토리지 구현체
│
├── llm/                  # LLM 연동 및 JSON 계획 파서/보안 검증 모듈
│   ├── client.py         # HTTP LLMClient & HTTPX 연결 관리 (120초 타임아웃)
│   ├── parser.py         # LLM 응답 JSON/Markdown 파싱기
│   ├── retry.py          # 지수 백오프 기반 LLM 재시도 실행기
│   ├── schemas.py        # Action Plan 액션 DTO
│   └── validator.py      # 경로 및 도구 허용 목록(openscad) 선검증기
│
├── runner/               # CLI 실행 및 프로세스 제어 모듈
│   ├── service.py        # CLIExecutionRunner (Semaphore 2개, 30초 Timeout, 인자 검증)
│   └── validator.py      # OS Command Injection 방어를 위한 인자 검증기
│
├── sse/                  # SSE 실시간 푸시 및 이벤트 스트리밍 모듈
│   ├── service.py        # SSEStreamService (재연결, 백오프, 스트림 종료 전송)
│   ├── connection_registry.py  # 동시 20개 커넥션 관리 레지스트리
│   └── security.py       # X-Stream-Token 생성 및 검증 서비스
│
├── orchestrator/         # 비동기 전체 파이프라인 제어 패키지
│   ├── service.py        # JobOrchestratorService (비동기 Job 전체 흐름 제어)
│   ├── concurrency.py    # 오케스트레이터 동시 실행 2개 제한 (10분 대기 제한)
│   ├── recovery.py       # 15분 경과 stale RUNNING Job 자동 실패 복구 서비스
│   └── actions.py        # 계획된 액션(CREATE_DIR, WRITE_FILE 등) 순차 디스패처
│
├── tests/                # 테스트 스위트
│   ├── conftest.py       # pytest 데이터베이스 및 클라이언트 격리 픽스처
│   ├── test_unit_1.py    # API Core & Storage 단위 테스트
│   ├── test_unit_2.py    # LLM Parser & Validator 단위 테스트
│   ├── test_unit_3.py    # CLI Runner 단위 테스트
│   ├── test_unit_4.py    # SSE Streaming & 복원 단위 테스트
│   └── test_unit_5.py    # Orchestrator & Stale Recovery 단위 테스트
│
└── aidlc-docs/           # AI-DLC 소프트웨어 수명주기 설계 산출물 문서 보관
```

---

## 🚦 시작 가이드

> **MVP 지원 환경**: Linux 서버와 WSL2만 지원합니다. 네이티브 Windows Python 및 Windows OpenSCAD 실행은 지원하지 않습니다.

### 1. 환경 변수 설정

`.env.sample`을 복사한 뒤 기존 PostgreSQL과 LLM 연결 정보를 입력합니다.

```bash
cp .env.sample .env
```

Windows/SlowAPI 인코딩 호환성을 위해 `.env.sample`과 실제 `.env`의 주석 및 값은 ASCII 문자만 사용하십시오. 실제 `.env`는 Git이나 Docker 이미지에 포함하면 안 됩니다.

데이터베이스는 Docker Compose가 생성하지 않습니다. `DATABASE_URL`의 hostname은 컨테이너에서 접근 가능해야 합니다. DB가 Docker host에서 실행되는 경우 `localhost` 대신 `host.docker.internal`을 사용합니다.

### 2. Docker Compose 실행 (권장)

WSL2 또는 Linux에서 실행합니다.

```bash
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs -f app
```

서비스가 healthy 상태가 되면 [http://localhost:8000/docs](http://localhost:8000/docs)에서 API를 확인합니다.

OpenSCAD 설치 확인:

```bash
docker compose exec app /usr/local/bin/openscad-headless --version
```

종료 시 workspace volume을 보존하려면 `-v`를 사용하지 않습니다.

```bash
docker compose down
```

`docker compose down -v`는 Job workspace와 artifact를 삭제하므로 데이터 삭제가 명확히 필요한 경우에만 사용하십시오.

### 3. WSL2에서 직접 실행

Docker 없이 개발할 때도 WSL2 Linux shell에서 실행합니다.

```bash
sudo apt-get update
sudo apt-get install -y openscad xvfb

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

xvfb-run -a uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

오케스트레이션 오류 traceback은 서버 console에 기록됩니다. Docker 환경에서는 `docker compose logs -f app`으로 확인합니다.

---

## 🧪 테스트 실행

SQLite 인메모리 DB를 사용하므로 별도의 PostgreSQL 설정 없이 전체 테스트 자동 실행이 가능합니다.

```bash
# 1. 전체 테스트 실행
python -m pytest -q

# 2. 상세 실행 및 디버그용 출력
python -m pytest -v

# 3. 특정 단위 테스트 개별 실행
python -m pytest tests/test_unit_5.py -v

# 4. 배포 구성 정적 테스트
python -m pytest tests/test_deployment.py -v
```
