# 인프라 설계 - Hotfix R-13 Linux/Docker Runtime

## 1. 배포 대상

- **로컬 Windows 개발**: WSL2 내부 Docker Engine 또는 WSL2 backend를 사용하는 Docker Desktop
- **Linux 배포**: Docker Engine과 Docker Compose V2
- **지원하지 않음**: 네이티브 Windows Python 실행, Windows container, Kubernetes, Docker Swarm
- **배포 단위**: 애플리케이션 컨테이너 1개
- **데이터베이스**: Compose 외부의 기존 PostgreSQL

## 2. 이미지 명세

### Base Image

- `python:3.13-slim-bookworm` 계열을 사용한다.
- Python 3.13은 현재 개발 환경과 일치시키고 Debian Bookworm은 OpenSCAD 패키지 설치 경로를 제공한다.

### OS 패키지

- `openscad`: 모델 변환 CLI
- `xvfb`: 디스플레이 없는 PNG 렌더링
- `ca-certificates`: 외부 HTTPS LLM endpoint 연결
- 패키지는 `--no-install-recommends`로 설치하고 apt list를 같은 layer에서 제거한다.

### Headless Adapter

- `/usr/local/bin/openscad-headless` 고정 wrapper를 이미지에 설치한다.
- wrapper는 `exec xvfb-run -a /usr/bin/openscad "$@"`만 수행한다.
- Python Runner는 wrapper를 `shell=False`로 실행하므로 action argument가 단일 문자열 command로 재해석되지 않는다.
- 컨테이너 환경의 `OPENSCAD_BIN_PATH`는 `/usr/local/bin/openscad-headless`로 고정한다.

### Python 및 프로세스 설정

- `PYTHONDONTWRITEBYTECODE=1`
- `PYTHONUNBUFFERED=1`
- 작업 디렉터리 `/app`
- Uvicorn command: `uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1`
- 애플리케이션 사용자는 고정 비루트 UID/GID `10001`을 사용한다.

## 3. Docker Compose 명세

### Application Service

| 항목 | 값 |
| --- | --- |
| 서비스명 | `app` |
| build context | 저장소 root |
| container port | `8000` |
| host port | `${APP_PORT:-8000}` |
| env file | `.env` |
| workspace mount | `workspace_data:/app/.workspaces` |
| restart | `unless-stopped` |
| CPU 기본 한도 | `2.0` |
| memory 기본 한도 | `2g` |
| Uvicorn workers | `1` |

### 보안 옵션

- `user: "10001:10001"`
- `security_opt: ["no-new-privileges:true"]`
- `cap_drop: ["ALL"]`
- Docker socket과 호스트 root를 mount하지 않는다.
- `.env`는 build context에서 제외하고 runtime에만 읽는다.

### Healthcheck

- Python 표준 라이브러리 `urllib.request`로 `http://127.0.0.1:8000/`을 호출한다.
- 제안값: interval 30초, timeout 5초, retries 3회, start period 20초.
- healthcheck는 FastAPI process 응답성을 검사하며 외부 DB 전체 가용성을 직접 검사하지 않는다.

## 4. Storage 설계

### Workspace Volume

- Compose top-level volume `workspace_data`를 선언한다.
- mount target은 `/app/.workspaces`다.
- 신규 named volume은 이미지의 `/app/.workspaces` 소유권을 이어받아 UID 10001이 쓸 수 있어야 한다.
- Job 입력, 중간 파일과 artifact가 동일 volume 아래에서 분리된 디렉터리를 사용한다.

### 외부 DB

- Compose에 DB service 또는 DB volume을 정의하지 않는다.
- `DATABASE_URL`은 `.env` 또는 shell environment에서 앱 service로 전달한다.
- 연결 문자열의 hostname은 컨테이너에서 도달 가능해야 한다.
- DB가 호스트에서 실행될 경우 `localhost`는 컨테이너 자신을 의미하므로 `host.docker.internal` 또는 접근 가능한 호스트 주소를 사용해야 한다.
- 실제 DB 비밀번호가 포함된 예시는 문서나 Compose에 기록하지 않는다.

## 5. Network 설계

- Compose 기본 bridge network를 사용한다.
- inbound는 host의 `${APP_PORT:-8000}`에서 앱 container 8000으로만 연결한다.
- outbound는 외부 PostgreSQL과 LLM HTTPS endpoint에 필요하다.
- reverse proxy, TLS termination, load balancer와 public ingress는 MVP 범위 밖이다.

## 6. 관측성과 장애 처리

- Python logging과 Uvicorn access/error log를 stdout/stderr로 출력한다.
- `docker compose logs -f app`으로 startup, DB, LLM, orchestration, CLI 오류를 확인한다.
- 오케스트레이션 예외는 `job_id`, 예외 타입과 traceback을 ERROR로 기록한다.
- Job 상태와 사용자 표시 이벤트는 기존 외부 DB의 EventLog에 계속 저장한다.
- container log driver는 Docker 기본값을 사용하며 중앙 수집과 보존 정책은 범위 밖이다.

## 7. 배포 파일 목록

| 파일 | 책임 |
| --- | --- |
| `Dockerfile` | Python, OpenSCAD, Xvfb, 비루트 사용자 및 Uvicorn 이미지 정의 |
| `docker-compose.yml` | 앱 service, runtime env, port, volume, healthcheck, 자원·보안 옵션 정의 |
| `.dockerignore` | 비밀, venv, workspace, Git 및 cache의 build context 제외 |
| `docker/openscad-headless` | 고정 Xvfb/OpenSCAD 실행 adapter |
| `.env.sample` | ASCII-only 공개 환경 변수 템플릿 |
| `README.md` | WSL2 및 Docker Compose 실행·검증 절차 |

## 8. 구현 순서와 의존성

1. `.dockerignore`와 headless adapter 작성
2. Dockerfile 작성 및 비루트 workspace 권한 설정
3. Docker Compose 앱 service와 named volume 작성
4. CLI Runner의 Job workspace `cwd` 수정
5. Orchestrator ERROR traceback 수정
6. 환경 템플릿과 README 갱신
7. 정적·단위·이미지·Compose smoke test 실행

## 9. 롤백

- 새 Docker 산출물을 제거해도 기존 WSL2 직접 Python 실행은 유지된다.
- Runner `cwd`와 Orchestrator logging 수정은 독립적으로 되돌릴 수 있다.
- named volume은 롤백 시 자동 삭제하지 않으며 사용자가 명시적으로 데이터 보존 여부를 결정한다.
- 외부 DB schema 변경은 없으므로 DB rollback은 필요하지 않다.
