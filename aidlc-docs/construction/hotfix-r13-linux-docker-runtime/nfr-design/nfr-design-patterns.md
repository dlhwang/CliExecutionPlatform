# NFR 설계 패턴 - Hotfix R-13 Linux/Docker Runtime

## 1. Single-Service Compose Boundary Pattern

### 목적

MVP 배포 책임을 애플리케이션 하나로 제한하고 기존 외부 DB의 수명주기와 분리한다.

### 설계

- `docker-compose.yml`은 애플리케이션 서비스 하나와 workspace named volume 하나만 선언한다.
- DB, Redis, worker, reverse proxy 서비스는 포함하지 않는다.
- 애플리케이션 컨테이너는 API, background orchestration, CLI Runner를 한 Uvicorn 프로세스에서 실행한다.
- Uvicorn worker 수는 1로 고정한다. 기존 프로세스 전역 세마포어가 CLI 동시 실행 2개를 정확히 제한하도록 하기 위함이다.
- 포트, env file, healthcheck, restart policy, volume 및 보안 옵션을 Compose가 조정한다.

### 확장성 경계

단일 replica는 명시적인 MVP 제약이다. replica를 늘리려면 분산 queue, 전역 동시성 제한, 공유 artifact storage와 Job 소유권 조정이 선행되어야 하며 R-13에서는 수행하지 않는다.

## 2. Immutable Image and Runtime Configuration Pattern

### 목적

동일한 이미지로 환경별 설정을 바꾸고 비밀정보가 build layer에 포함되지 않도록 한다.

### 설계

- Dockerfile은 애플리케이션 코드와 공개 의존성만 복사한다.
- `.dockerignore`는 `.env`, 가상환경, Git metadata, cache, workspace 및 로컬 테스트 산출물을 제외한다.
- `DATABASE_URL`, LLM 설정과 SSE 비밀 키는 Compose `env_file` 또는 runtime environment로 주입한다.
- Dockerfile과 Compose에는 실제 비밀번호나 API 키를 기록하지 않는다.
- Python은 bytecode와 출력 buffering을 비활성화해 read-only 성격과 즉시 로그 출력을 지원한다.

### 실패 정책

필수 설정 또는 외부 DB 연결이 잘못된 경우 잘못된 로컬 기본 DB로 대체하지 않고 startup 실패와 원인을 stdout/stderr에 남긴다.

## 3. Persistent Workspace Volume Pattern

### 목적

컨테이너 수명과 Job workspace 및 artifact 수명을 분리한다.

### 설계

- named volume을 `/app/.workspaces`에 연결한다.
- `LocalStorageService`와 `CLIExecutionRunner`는 동일한 기본 경로를 사용한다.
- workspace 생성 시 `/app/.workspaces/jobs/{job_id}`와 `/app/.workspaces/artifacts/{job_id}`를 생성한다.
- CLI subprocess `cwd`는 Job jobs 디렉터리의 검증된 절대경로다.
- 컨테이너의 비루트 사용자 UID/GID가 volume에 쓸 수 있도록 이미지 초기 디렉터리 권한을 설정한다.

### 불변 조건

- `cwd`는 반드시 `base_dir/jobs/{job_id}` 아래여야 한다.
- action argument는 계속 상대경로만 허용한다.
- Docker socket, 호스트 루트 또는 임의 호스트 디렉터리를 기본으로 mount하지 않는다.

## 4. Restricted Container Execution Pattern

### 목적

OpenSCAD 실행 권한을 필요한 범위로 제한한다.

### 설계

- 컨테이너 프로세스는 비루트 사용자로 실행한다.
- Compose는 `no-new-privileges`를 설정하고 불필요한 Linux capability를 제거한다.
- subprocess는 `shell=False`인 `asyncio.create_subprocess_exec`로만 시작한다.
- 쓰기 가능한 영속 경로는 workspace volume으로 제한하고 임시 파일이 필요하면 `/tmp`를 사용한다.
- CPU와 메모리 한도는 Compose에서 설정 가능하게 하고 smoke test로 기본값을 검증한다.

## 5. Workspace-Bound Async Subprocess Pattern

### 목적

Linux에서 CLI를 비차단 실행하고 상대경로를 정확한 Job workspace에 고정한다.

### 설계

- `CLIExecutionRunner.run_tool`은 `job_id`로 workspace 절대경로를 계산한다.
- 계산한 경로가 존재하는 디렉터리이며 jobs root 아래인지 확인한다.
- `_launch_with_retry`에 이 경로를 `cwd`로 전달한다.
- 30초 timeout, 최대 동시 실행 2개, launch OSError 재시도 2회, stdout/stderr 병합 정책을 유지한다.
- 네이티브 Windows event loop fallback은 구현하지 않는다. 공식 런타임은 Linux다.

### 실패 처리

- workspace가 없거나 경계를 벗어나면 subprocess를 시작하지 않고 명시적인 launch 오류를 발생시킨다.
- non-zero exit, timeout 및 argument validation 오류는 기존 예외 계층으로 전달한다.

## 6. Headless OpenSCAD Adapter Pattern

### 목적

디스플레이가 없는 컨테이너에서 STL과 PNG 생성을 모두 지원한다.

### 설계

- 이미지에 Linux OpenSCAD와 headless 렌더링에 필요한 런타임을 설치한다.
- 컨테이너의 `OPENSCAD_BIN_PATH`는 직접 실행 가능한 단일 바이너리 또는 wrapper 경로를 가리킨다.
- wrapper가 필요한 경우 고정된 OpenSCAD 실행만 위임하며 사용자 입력을 shell 문자열로 결합하지 않는다.
- STL smoke test와 PNG smoke test를 분리하여 headless 렌더링 실패를 식별한다.

### 선택 기준

offscreen 환경 변수만으로 PNG가 성공하면 추가 wrapper를 만들지 않는다. 실패할 경우 Xvfb 기반 고정 wrapper를 사용한다. 최종 선택은 Infrastructure Design의 이미지 검증에서 확정한다.

## 7. Dual-Sink Failure Observability Pattern

### 목적

사용자용 EventLog와 운영자용 서버 traceback을 동시에 보존한다.

### 설계

- 오케스트레이션 최상위 예외 처리 진입 즉시 `logger.exception`으로 원본 traceback을 stdout/stderr에 기록한다.
- 로그 문맥에는 `job_id`와 예외 타입을 포함한다.
- 그 후 기존 repository transition으로 `ORCHESTRATION_FAILED` EventLog와 FAILED 상태를 저장한다.
- 예외 문자열이 비어 있어도 타입과 traceback으로 원인을 확인할 수 있다.
- prompt, 전체 action content, 환경 변수 및 비밀 값은 로그 문맥에서 제외한다.

### 복원력

EventLog 저장 자체가 실패하면 별도 `logger.exception`으로 기록해 원래 실패가 완전히 사라지지 않게 한다. 원래 예외를 사용자에게 재발생시키지 않는 기존 background task 계약은 유지한다.

## 8. Healthcheck and Restart Pattern

### 목적

Compose가 애플리케이션 프로세스 상태를 판별하고 일시적 프로세스 종료에서 복구하게 한다.

### 설계

- 기존 `GET /` 또는 별도 경량 endpoint를 컨테이너 내부 HTTP healthcheck에 사용한다.
- healthcheck는 프로세스 응답성을 검사하며 외부 DB의 전체 가용성을 health 상태와 강결합하지 않는다.
- restart policy는 비정상 프로세스 종료를 복구하되 로그를 stdout/stderr에 유지한다.
- 설정 오류로 반복 종료하는 경우 `docker compose logs`에서 원인을 확인할 수 있어야 한다.

## 9. 검증 패턴 매핑

| 설계 패턴 | 검증 방법 |
| --- | --- |
| Single-Service Compose Boundary | Compose 정적 파싱, 서비스 수 및 DB 서비스 부재 확인 |
| Runtime Configuration | 비밀 값 검색, `.dockerignore` 및 env 주입 확인 |
| Persistent Workspace Volume | volume mount 검사와 컨테이너 재생성 후 파일 보존 |
| Restricted Container Execution | 컨테이너 사용자와 security option 확인 |
| Workspace-Bound Async Subprocess | unit test로 `cwd`와 경계 오류 검증 |
| Headless OpenSCAD Adapter | STL 및 PNG container smoke test |
| Dual-Sink Failure Observability | `caplog`와 EventLog 동시 검증 |
| Healthcheck and Restart | `docker compose ps` health 상태 확인 |
