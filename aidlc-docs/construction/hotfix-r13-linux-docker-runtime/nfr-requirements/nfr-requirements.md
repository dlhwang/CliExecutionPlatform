# 비기능 요구사항 - Hotfix R-13 Linux/Docker Runtime

## 1. 범위와 운영 제약

- 공식 서버 실행 환경은 Linux다.
- Windows 호스트의 로컬 개발은 WSL2 Linux 환경만 지원한다.
- 네이티브 Windows Python과 Windows OpenSCAD 실행은 MVP 지원 범위에서 제외한다.
- 배포 진입점은 Docker Compose이며 Compose에는 애플리케이션 서비스 하나만 둔다.
- PostgreSQL 등 데이터베이스 서비스는 Compose에 포함하지 않고 기존 외부 DB에 연결한다.
- MVP는 애플리케이션 단일 replica로 운영한다. 프로세스 전역 세마포어와 로컬 workspace volume을 사용하므로 수평 확장은 이번 범위에서 지원하지 않는다.

## 2. 성능 및 리소스 요구사항

### NFR-R13-P1: API 비차단 처리

- Job 생성 API는 CLI 완료를 기다리지 않고 기존 백그라운드 오케스트레이션 계약을 유지한다.
- OpenSCAD 실행과 출력 수집은 Linux `asyncio` subprocess를 사용하며 HTTP event loop를 동기식 프로세스 대기로 차단하지 않는다.

### NFR-R13-P2: CLI 실행 한계

- 단일 CLI 실행 timeout은 기존 정책인 30초를 유지한다.
- 한 애플리케이션 프로세스에서 동시 OpenSCAD 실행은 최대 2개로 유지한다.
- timeout 시 하위 프로세스를 종료하고 회수한 뒤 TIMEOUT 이벤트를 영속화한다.
- stdout과 stderr는 기존처럼 하나의 순서 보장 스트림으로 수집한다.

### NFR-R13-P3: 컨테이너 자원 통제

- Docker Compose는 CPU와 메모리 한도를 설정할 수 있는 구조로 작성한다.
- 초기 기본값은 OpenSCAD smoke test로 검증하고, 환경별 조정 방법을 README에 기록한다.
- 이미지 빌드 시 불필요한 캐시와 개발 파일을 제외해 이미지 크기와 공격 표면을 줄인다.

## 3. 신뢰성 및 가용성 요구사항

### NFR-R13-R1: Workspace 영속성

- `.workspaces`는 Docker named volume 또는 동등한 외부 volume에 연결한다.
- 컨테이너 재생성 후에도 Job workspace와 artifact 파일이 보존되어야 한다.
- OpenSCAD subprocess의 working directory는 `.workspaces/jobs/{job_id}`의 절대경로여야 한다.

### NFR-R13-R2: 외부 DB 연결

- 컨테이너는 런타임에 전달된 `DATABASE_URL`을 사용한다.
- DB 접속 정보는 이미지에 포함하지 않는다.
- Compose는 DB 컨테이너를 생성하거나 DB 수명주기를 관리하지 않는다.
- DB 호스트명은 컨테이너 네트워크에서 도달 가능한 주소여야 하며 이 제약을 문서화한다.
- DB 연결 실패 시 원인을 서버 로그에서 확인할 수 있어야 하며 잘못된 로컬 DB로 자동 대체하지 않는다.

### NFR-R13-R3: 서비스 상태 확인

- Compose 애플리케이션 서비스는 HTTP healthcheck를 제공한다.
- 프로세스 비정상 종료 시 재시작 정책을 적용하되, 지속적인 설정 오류가 무한히 은폐되지 않도록 로그를 보존한다.

## 4. 보안 요구사항

### NFR-R13-S1: 컨테이너 최소 권한

- 애플리케이션은 비루트 사용자로 실행한다.
- `shell=True`는 사용하지 않으며 OpenSCAD 바이너리와 인자 목록을 분리한다.
- Linux capability는 애플리케이션 실행에 필요한 최소 수준으로 제한한다.
- workspace volume 외 애플리케이션 데이터 경로에 대한 불필요한 쓰기 권한을 부여하지 않는다.

### NFR-R13-S2: 비밀정보 보호

- `.env`, API 키, DB 비밀번호, SSE 비밀 키는 Docker build context와 이미지 layer에서 제외한다.
- Dockerfile과 `docker-compose.yml`에는 실제 비밀 값을 하드코딩하지 않는다.
- 런타임 설정은 환경 변수 또는 로컬 env 파일로 주입하며 env 파일은 버전 관리 대상에서 제외한다.
- 서버 로그에 전체 환경 변수, DB URL의 비밀번호, LLM API 키 또는 SSE 토큰을 기록하지 않는다.

### NFR-R13-S3: 경로 격리 유지

- 기존 상대경로 allowlist와 traversal 방어를 유지한다.
- CLI working directory 변경이 workspace 경계 검증을 우회해서는 안 된다.
- 컨테이너에 Docker socket 또는 호스트 루트 파일시스템을 마운트하지 않는다.

## 5. 관측성 요구사항

### NFR-R13-O1: 서버 오류 로그

- 처리된 오케스트레이션 예외도 `ERROR` 수준으로 stdout/stderr에 기록한다.
- 로그에는 `job_id`, 예외 타입, 예외 메시지와 traceback을 포함한다.
- EventLog의 기존 `ORCHESTRATION_FAILED` 계약은 유지한다.
- 메시지가 없는 예외도 예외 타입과 실행 문맥으로 식별할 수 있어야 한다.

### NFR-R13-O2: 컨테이너 로그

- 애플리케이션 로그는 컨테이너 stdout/stderr로 출력하고 컨테이너 내부 파일 로그에 의존하지 않는다.
- `docker compose logs`로 시작 실패, DB 연결 실패, 오케스트레이션 실패를 확인할 수 있어야 한다.

## 6. OpenSCAD 호환성 요구사항

- Docker 이미지에 Linux OpenSCAD CLI를 포함한다.
- STL 생성은 디스플레이 서버 없이 동작해야 한다.
- PNG preview가 필요한 action은 headless 렌더링 구성을 통해 동작해야 한다.
- 이미지 내부에서 OpenSCAD 버전 확인과 최소 SCAD 변환 smoke test를 실행할 수 있어야 한다.
- `OPENSCAD_BIN_PATH` 기본값은 컨테이너 내부 실행 경로와 일치해야 한다.

## 7. 유지보수성 및 검증 요구사항

- `Dockerfile`, `docker-compose.yml`, `.dockerignore`의 역할과 실행 명령을 README에 기록한다.
- WSL2 직접 실행과 Docker Compose 실행 절차를 구분해 문서화한다.
- 단위 테스트는 CLI `cwd`와 ERROR traceback을 직접 검증한다.
- 정적 검증은 Compose에 DB 서비스가 없고 실제 비밀 값이 포함되지 않았음을 확인한다.
- 컨테이너 smoke test는 이미지 빌드, OpenSCAD 실행, FastAPI import 또는 healthcheck를 검증한다.
- 전체 `pytest` 회귀 테스트가 통과해야 한다.

## 8. 제외 범위

- 네이티브 Windows 실행 호환성
- 다중 애플리케이션 replica와 분산 세마포어
- Kubernetes, Swarm 및 외부 queue 도입
- PostgreSQL 컨테이너 생성과 DB 백업·복구 자동화
- 중앙 로그 수집 시스템과 alerting 플랫폼 구축
