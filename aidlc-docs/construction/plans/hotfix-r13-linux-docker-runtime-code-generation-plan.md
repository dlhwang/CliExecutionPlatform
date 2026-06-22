# Hotfix R-13 Code Generation 계획

이 문서는 R-13 Code Generation Part 2의 단일 실행 기준이다. 각 단계는 순서대로 수행하고 완료한 동일 interaction에서 즉시 `[x]`로 변경한다.

## 1. Unit Context

- **Unit**: `hotfix-r13-linux-docker-runtime`
- **Workspace Root**: `D:\workspace\CLI-Execution-Platform`
- **Project Type**: Python/FastAPI brownfield
- **Approved Requirement**: R-13 Linux 실행 환경 표준화, Docker Compose 배포, 외부 DB 연결, CLI workspace `cwd`, 서버 traceback
- **User Stories**: N/A - 인프라 및 내부 실행 장애 변경으로 User Stories 단계 생략
- **Database Ownership**: 기존 외부 DB와 schema를 유지하며 migration 없음
- **API Contract**: 기존 Job/API/SSE 계약 변경 없음
- **Runtime Boundary**: Linux/WSL2, Docker Compose 앱 단일 service, Uvicorn 단일 worker

## 2. Dependencies and Existing Changes

- `LocalStorageService`와 `CLIExecutionRunner`는 기본 `.workspaces` root를 공유한다.
- `ActionExecutor`가 `job_id`를 Runner에 전달하므로 공개 인터페이스 변경 없이 `cwd`를 계산할 수 있다.
- `orchestrator/service.py`와 `tests/test_unit_5.py`에는 기존 R-10 dirty 변경이 있다. 해당 변경을 보존하고 R-13 로깅만 최소 추가한다.
- `llm/client.py`, 기존 R-12 문서 변경과 다른 dirty 파일은 R-13 구현에서 불필요하게 수정하지 않는다.
- 네이티브 Windows subprocess fallback은 구현하지 않는다.

## 3. Generation Steps

### Step 1: Dirty Worktree 및 구현 경계 확인

- [x] `git status --short`와 대상 파일 diff를 다시 확인한다.
- [x] R-10/R-12 기존 변경과 R-13 변경의 겹침을 기록하고 사용자 변경을 보존한다.
- [x] Docker/Compose 신규 파일이 기존 파일과 충돌하지 않는지 확인한다.

### Step 2: Docker 이미지 및 Headless OpenSCAD 산출물 생성

- [x] Workspace root에 `Dockerfile`을 생성한다.
- [x] `python:3.13-slim-bookworm`, `openscad`, `xvfb`, `ca-certificates`를 구성한다.
- [x] 고정 UID/GID 10001 비루트 사용자와 `/app/.workspaces` 권한을 구성한다.
- [x] `docker/openscad-headless` wrapper를 생성하고 인자를 `"$@"`로 그대로 전달한다.
- [x] Uvicorn 단일 worker 실행 command와 컨테이너 `OPENSCAD_BIN_PATH`를 설정한다.
- [x] `.dockerignore`를 생성해 `.env`, venv, Git, cache, workspace와 로컬 산출물을 제외한다.

### Step 3: Docker Compose 애플리케이션 서비스 생성

- [x] Workspace root에 `docker-compose.yml`을 생성한다.
- [x] 앱 service 하나만 정의하고 DB service는 정의하지 않는다.
- [x] `.env` runtime 주입, `${APP_PORT:-8000}:8000`, `workspace_data:/app/.workspaces`를 설정한다.
- [x] 단일 worker, 비루트 UID 10001, `no-new-privileges`, capability 제거를 적용한다.
- [x] CPU 2.0, memory 2g, `unless-stopped`, HTTP healthcheck를 적용한다.
- [x] named volume `workspace_data`를 선언한다.

### Step 4: CLI Runner를 Job Workspace 기준으로 수정

- [x] `runner/service.py`에서 `base_dir/jobs/{job_id}`를 resolve하는 내부 메서드를 추가한다.
- [x] workspace가 존재하는 디렉터리이며 jobs root 하위인지 검증한다.
- [x] `_launch_with_retry`에 검증된 workspace 절대경로를 `cwd`로 전달한다.
- [x] 기존 timeout, semaphore, launch retry와 stream 수집 동작을 유지한다.
- [x] 잘못된 workspace 실패가 진단 가능한 예외 문맥을 제공하도록 한다.

### Step 5: CLI Workspace 단위 테스트 추가

- [x] `tests/test_unit_3.py`에 subprocess `cwd`가 Job workspace 절대경로인지 검증하는 테스트를 추가한다.
- [x] workspace 부재 또는 경계 위반 시 subprocess가 시작되지 않는 테스트를 추가한다.
- [x] 기존 성공, timeout, retry, exit code 및 semaphore 테스트를 실행한다.

### Step 6: Orchestrator 서버 Traceback 로깅 추가

- [x] `orchestrator/service.py`에 모듈 logger를 추가한다.
- [x] 오케스트레이션 예외 포착 즉시 `logger.exception`으로 `job_id`와 예외 타입을 기록한다.
- [x] 기존 R-10 `ORCHESTRATION_FAILED` EventLog 상세 메시지를 유지한다.
- [x] EventLog transition 실패도 서버 로그로 확인 가능하도록 방어한다.
- [x] prompt, action content 및 비밀 설정을 로그에 포함하지 않는다.

### Step 7: Orchestrator 로깅 테스트 추가

- [x] `tests/test_unit_5.py`의 기존 R-10 상세 이벤트 테스트를 보존한다.
- [x] `caplog`로 ERROR level, `job_id`, 예외 타입과 traceback을 검증한다.
- [x] repository transition 실패 시 서버 로그가 남는 경계 테스트 필요성을 평가하고 추가한다.

### Step 8: 배포 정적 검증 테스트 생성

- [x] `tests/test_deployment.py`를 생성한다.
- [x] Dockerfile이 OpenSCAD/Xvfb, 비루트 사용자와 단일 Uvicorn worker를 포함하는지 검증한다.
- [x] `.dockerignore`가 `.env`와 `.workspaces`를 제외하는지 검증한다.
- [x] Compose가 앱 service 하나, 외부 env, named volume, healthcheck를 가지며 DB service가 없는지 검증한다.
- [x] Dockerfile과 Compose에 실제 `.env` 비밀 값이 포함되지 않았는지 검증한다.

### Step 9: 환경 템플릿과 실행 문서 갱신

- [x] `.env.sample`을 ASCII-only로 유지하면서 Docker/WSL2 변수와 외부 DB hostname 제약을 반영한다.
- [x] README에서 네이티브 Windows 실행을 지원 대상에서 제외한다.
- [x] WSL2 직접 실행과 `docker compose up --build` 절차를 구분해 작성한다.
- [x] 외부 DB는 Compose가 생성하지 않으며 container에서 도달 가능한 hostname이 필요함을 설명한다.
- [x] 로그 확인, health 상태, OpenSCAD smoke test, volume 보존 및 안전한 종료 절차를 문서화한다.

### Step 10: 검증 실행 및 코드 요약 작성

- [x] 변경 대상 Python 파일의 관련 단위 테스트를 실행한다.
- [x] 전체 `pytest -q` 회귀 테스트를 실행한다.
- [x] `docker compose config`로 Compose 구문과 service 구조를 검증한다. (N/A: Docker CLI 미설치, 정적 구조 테스트로 대체)
- [x] Docker 사용 가능 시 `docker compose build`를 실행한다. (N/A: Docker CLI 미설치)
- [x] Docker 사용 가능 시 컨테이너에서 OpenSCAD 버전, STL/PNG 생성과 HTTP healthcheck를 검증한다. (N/A: Docker CLI 미설치)
- [x] Docker를 사용할 수 없는 경우 실행하지 못한 항목을 N/A로 표시하고 정확한 사유와 후속 명령을 기록한다.
- [x] `aidlc-docs/construction/hotfix-r13-linux-docker-runtime/code/code-summary.md`를 작성한다.
- [x] 모든 단계와 요구사항 검증 결과를 확인하고 plan checkbox를 완료 처리한다.

## 4. Requirement Verification Mapping

| R-13 인수 기준 | 구현 파일 | 자동화 증거 |
| --- | --- | --- |
| Linux/OpenSCAD 이미지 | `Dockerfile`, `docker/openscad-headless` | `tests/test_deployment.py`, `docker compose build`, OpenSCAD smoke |
| Compose 앱 단일 service 및 외부 DB | `docker-compose.yml` | 정적 test, `docker compose config` |
| 비밀정보 이미지 비포함 | `.dockerignore`, Compose runtime env | 정적 test 및 diff 검사 |
| Workspace 영속성 | `docker-compose.yml` named volume | 정적 test, container 재생성 smoke |
| Job workspace `cwd` | `runner/service.py` | `tests/test_unit_3.py` |
| 서버 ERROR traceback | `orchestrator/service.py` | `tests/test_unit_5.py` `caplog` |
| WSL2/Docker 실행 문서 | `.env.sample`, `README.md` | 정적 review/test |
| 기존 API/SSE 회귀 없음 | 기존 application code | 전체 `pytest -q` |

## 5. Expected File Changes

### 신규 애플리케이션·배포 파일

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `docker/openscad-headless`
- `tests/test_deployment.py`

### 기존 파일 수정

- `runner/service.py`
- `orchestrator/service.py`
- `tests/test_unit_3.py`
- `tests/test_unit_5.py`
- `.env.sample`
- `README.md`

### 문서 산출물

- `aidlc-docs/construction/hotfix-r13-linux-docker-runtime/code/code-summary.md`

## 6. Completion Gate

- 모든 구현 단계 checkbox가 `[x]`다.
- R-13 자동화 테스트와 전체 회귀가 통과한다.
- Docker 실행 가능 환경에서는 Compose build와 OpenSCAD smoke가 통과한다.
- 실행 불가능한 검증은 N/A 사유와 재현 명령이 기록된다.
- 기존 dirty 변경을 덮어쓰거나 관련 없는 파일을 수정하지 않는다.
