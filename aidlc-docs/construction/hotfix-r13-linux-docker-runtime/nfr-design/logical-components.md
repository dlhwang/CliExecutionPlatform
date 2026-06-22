# 논리 컴포넌트 - Hotfix R-13 Linux/Docker Runtime

## 1. 컴포넌트 목록

| 컴포넌트 | 책임 | 변경 유형 |
| --- | --- | --- |
| Docker Image Definition | Python 앱, OpenSCAD, headless runtime, 비루트 사용자 패키징 | 신규 |
| Compose Application Service | 포트, 환경 변수, volume, healthcheck, 자원 및 보안 옵션 선언 | 신규 |
| Workspace Volume | Job workspace와 artifact의 컨테이너 외부 영속성 제공 | 신규 |
| External Database Boundary | 주입된 `DATABASE_URL`로 기존 DB 연결 | 구성 |
| `LocalStorageService` | `/app/.workspaces` 하위 Job 및 artifact 경로 관리 | 기존 유지 |
| `CLIExecutionRunner` | 검증된 Job workspace `cwd`에서 Linux OpenSCAD 실행 | 수정 |
| Headless OpenSCAD Adapter | 디스플레이 없는 환경에서 STL/PNG 실행 경로 제공 | 신규 또는 이미지 구성 |
| `JobOrchestratorService` | background 실패의 EventLog 저장과 서버 traceback 기록 | 수정 |
| Container Healthcheck | FastAPI 프로세스 응답성 검사 | 신규 구성 |

## 2. 런타임 경계

### 2.1 Compose Application Service

입력 구성:

- `DATABASE_URL`
- `LLM_ENDPOINT`, `LLM_API_KEY`, `LLM_MODEL`
- `SSE_STREAM_TOKEN_SECRET`
- `APP_ENV`
- 컨테이너 내부 `OPENSCAD_BIN_PATH`

노출 자원:

- 호스트 포트에서 컨테이너 `8000` 포트로 연결
- named volume에서 `/app/.workspaces`로 연결
- stdout/stderr container log

명시적 비포함:

- DB service
- Docker socket
- 호스트 루트 mount
- 실제 `.env` 파일의 이미지 복사

### 2.2 External Database Boundary

- 애플리케이션은 SQLAlchemy의 기존 `DATABASE_URL` 처리 경로를 사용한다.
- DB schema와 connection pool 동작은 기존 코드 계약을 유지한다.
- Compose는 연결 정보를 전달할 뿐 DB 생성, healthcheck, migration 수명주기를 소유하지 않는다.
- 연결 주소는 컨테이너 네트워크에서 도달 가능해야 한다.

## 3. 파일 및 프로세스 경로

| 용도 | 컨테이너 경로 |
| --- | --- |
| 애플리케이션 root | `/app` |
| Workspace root | `/app/.workspaces` |
| Job 입력·중간 파일 | `/app/.workspaces/jobs/{job_id}` |
| Artifact 파일 | `/app/.workspaces/artifacts/{job_id}` |
| OpenSCAD 실행 파일 | Infrastructure Design에서 확정할 고정 Linux 경로 |

`CLIExecutionRunner` 협력 순서:

1. `ArgumentValidator`가 action argument를 검증한다.
2. Runner가 `base_dir/jobs/{job_id}`를 resolve한다.
3. 경로 존재와 root 하위 여부를 확인한다.
4. 전역 semaphore를 획득한다.
5. OpenSCAD를 `cwd=job_workspace`로 시작한다.
6. stdout/stderr를 EventLog에 저장한다.
7. timeout 또는 exit code를 처리하고 semaphore를 해제한다.

## 4. 오류 관측 컴포넌트 협력

`JobOrchestratorService` 실패 순서:

1. action 실행 중 예외를 포착한다.
2. `logger.exception`으로 `job_id`, 예외 타입과 traceback을 stdout/stderr에 기록한다.
3. repository transition으로 Job을 FAILED 처리하고 `ORCHESTRATION_FAILED` 이벤트를 추가한다.
4. transition 실패 시 그 실패도 서버 traceback으로 기록한다.
5. background task 반환값은 기존처럼 `False`를 유지한다.

## 5. 배포 산출물 책임

### Dockerfile

- Linux Python base image 선택
- Python dependency 설치
- OpenSCAD 및 headless dependency 설치
- 애플리케이션 코드 복사
- 비루트 사용자와 workspace 권한 설정
- Uvicorn 단일 worker 실행 명령 정의

### `.dockerignore`

- `.env`, `venv`, `.git`, cache, `.workspaces`, 테스트 임시 파일 제외
- 비밀정보와 로컬 산출물이 build context에 들어가지 않도록 차단

### `docker-compose.yml`

- 앱 단일 service와 workspace named volume 선언
- env file 또는 environment passthrough
- `8000` 포트, healthcheck, restart policy 선언
- 비루트 실행과 capability 제한 적용
- DB service를 선언하지 않음

## 6. 설계 제약 및 후속 결정

- 단일 Uvicorn worker만 지원한다.
- Compose replica 확장은 금지한다.
- OpenSCAD PNG smoke test 결과에 따라 offscreen 환경 변수 또는 Xvfb adapter를 Infrastructure Design에서 확정한다.
- CPU와 메모리 기본값은 Infrastructure Design에서 smoke test 가능성을 고려해 확정한다.
- 외부 DB 주소 예시에는 실제 비밀정보를 포함하지 않는다.

## 7. 요구사항 추적성

| 요구사항 | 담당 컴포넌트 |
| --- | --- |
| Linux/WSL2 공식 지원 | Docker Image Definition, README |
| Docker Compose 앱 단일 서비스 | Compose Application Service |
| 외부 DB 연결 | External Database Boundary |
| Workspace 영속성 | Workspace Volume, LocalStorageService |
| Job 기준 CLI `cwd` | CLIExecutionRunner |
| Headless OpenSCAD | Docker Image Definition, Headless OpenSCAD Adapter |
| ERROR traceback | JobOrchestratorService, stdout/stderr logging |
| 비밀정보 비포함 | Runtime Configuration, `.dockerignore` |
