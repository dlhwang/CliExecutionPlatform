# 기술 스택 결정 - Hotfix R-13 Linux/Docker Runtime

## 결정 요약

| 영역 | 선택 | 이유 |
| --- | --- | --- |
| 공식 서버 OS | Linux | `asyncio` subprocess와 OpenSCAD CLI의 일관된 실행 환경 제공 |
| Windows 로컬 개발 | WSL2 | 네이티브 Windows event loop 차이를 MVP 범위에서 제거 |
| 컨테이너 실행 | Docker Compose V2 | 단일 앱 서비스, 환경 변수, volume, healthcheck를 간결하게 선언 |
| 이미지 기반 | Python slim 계열 Linux 이미지 | Python 런타임과 Debian 패키지 기반 OpenSCAD 설치의 균형 |
| CLI 실행 | `asyncio.create_subprocess_exec`, `shell=False` | 기존 비차단 출력 수집과 명령어 주입 방어 유지 |
| OpenSCAD | Linux 패키지와 headless 실행 구성 | STL과 PNG 생성을 컨테이너에서 재현 |
| DB | 외부 PostgreSQL, `DATABASE_URL` 주입 | 사용자가 보유한 DB를 유지하고 Compose 책임을 앱으로 제한 |
| 파일 영속성 | Docker named volume을 `.workspaces`에 연결 | 컨테이너 교체 후 Job 및 artifact 보존 |
| 로그 | Python logging에서 stdout/stderr 출력 | `docker compose logs`와 직접 통합하고 별도 파일 로그를 피함 |
| 프로세스 모델 | Uvicorn 단일 worker | 인메모리 동시성 gate와 단일 volume 기반 MVP 계약 유지 |

## 세부 결정

### 1. Docker Compose 서비스 경계

- `docker-compose.yml`에는 API/오케스트레이터/CLI Runner를 포함한 애플리케이션 서비스 하나만 정의한다.
- DB, Redis, worker 서비스는 추가하지 않는다.
- 서비스는 외부 `DATABASE_URL`, LLM 설정, SSE 비밀 키를 런타임에 주입받는다.
- 애플리케이션 포트는 기본 `8000`을 노출한다.

### 2. 이미지 및 OpenSCAD

- Python slim 계열 Linux 이미지를 사용하고 OpenSCAD를 OS 패키지로 설치한다.
- 빌드 도구와 패키지 cache는 최종 이미지에 불필요하게 남기지 않는다.
- 비루트 애플리케이션 사용자를 생성하고 `.workspaces` 쓰기 권한만 부여한다.
- PNG 렌더링은 headless 환경에서 검증한다. OpenSCAD의 offscreen 실행만으로 부족한 경우 Xvfb wrapper를 사용하되 shell command 문자열은 사용하지 않는다.

### 3. 외부 DB 연결

- `DATABASE_URL`은 Compose environment 또는 env file로 전달한다.
- Dockerfile은 `.env`를 복사하지 않으며 `.dockerignore`가 이를 차단한다.
- 연결 문자열의 호스트는 컨테이너에서 접근 가능해야 한다. 호스트 DB를 사용하는 개발 환경은 WSL2/Docker 네트워크에 맞는 주소를 사용하도록 문서화한다.

### 4. Workspace와 artifact

- Compose named volume을 애플리케이션의 `/app/.workspaces`에 연결한다.
- CLI Runner의 기본 `base_dir`와 Compose mount 경로가 동일한 논리 경로를 사용한다.
- subprocess `cwd`는 `/app/.workspaces/jobs/{job_id}`로 계산하고 해당 디렉터리 존재와 경계를 검증한다.

### 5. 관측성과 오류 처리

- `orchestrator.service`에 모듈 logger를 추가한다.
- 최상위 오케스트레이션 예외 처리에서 `logger.exception`을 사용해 traceback을 남긴다.
- 구조화 필드 또는 메시지에 `job_id`와 예외 타입을 포함하지만 요청 prompt와 비밀 설정은 포함하지 않는다.
- DB EventLog 기록 실패가 원래 traceback 출력을 막지 않도록 로깅 순서를 설계 단계에서 검토한다.

## 거절한 대안

| 대안 | 거절 이유 |
| --- | --- |
| 네이티브 Windows 호환 fallback 구현 | MVP 범위를 늘리고 Linux 배포 환경과 다른 프로세스 경로를 유지해야 함 |
| Compose에 PostgreSQL 포함 | 사용자가 기존 DB를 보유하며 DB 수명주기는 이번 서비스 범위가 아님 |
| 동기식 `subprocess.run` | FastAPI event loop와 SSE 로그 수집을 차단할 수 있음 |
| 다중 Uvicorn worker | 인메모리 세마포어가 worker별로 분리되고 CLI 동시성 상한이 깨짐 |
| 컨테이너 내부 파일 로그 | 컨테이너 교체 시 로그 유실과 별도 volume 관리가 필요함 |

## 검증 결정

- 단위: CLI `cwd`, 오케스트레이션 ERROR traceback
- 정적: Compose 앱 단일 서비스, DB 서비스 부재, 비밀 하드코딩 부재
- 빌드: `docker compose build`
- smoke: OpenSCAD 버전 및 최소 SCAD 변환, FastAPI healthcheck
- 회귀: 전체 `pytest` 실행
