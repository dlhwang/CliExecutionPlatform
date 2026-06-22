# Hotfix R-13 코드 생성 요약

## 구현 결과

Linux/WSL2를 공식 실행 환경으로 제한하고 OpenSCAD를 포함한 Docker Compose 앱 단일 서비스 배포 구성을 추가했다. CLI는 Job workspace에서 실행되며 오케스트레이션 실패는 EventLog와 서버 traceback 양쪽에 기록된다.

## 생성 파일

- `Dockerfile`: Python 3.13 slim, OpenSCAD, Xvfb, xauth, 비루트 UID 10001 및 Uvicorn 단일 worker
- `.dockerignore`: `.env`, venv, Git, cache, workspace 및 로컬 산출물 제외
- `docker-compose.yml`: 앱 단일 service, 외부 env, named volume, healthcheck, 2 CPU/2GB, 최소 권한
- `docker/openscad-headless`: Xvfb 기반 고정 OpenSCAD adapter
- `tests/test_deployment.py`: 이미지·Compose·비밀 제외·ASCII 템플릿 정적 검증

## 수정 파일

- `runner/service.py`: `base_dir/jobs/{job_id}` 검증 및 subprocess `cwd` 적용
- `orchestrator/service.py`: `job_id`와 예외 타입을 포함한 ERROR traceback 및 transition 실패 로깅
- `tests/test_unit_3.py`: 임시 Job workspace 적용, `cwd`와 workspace 부재 테스트 추가
- `tests/test_unit_5.py`: 기존 R-10 상세 EventLog 테스트 보존, `caplog` traceback과 transition 실패 테스트 추가
- `.env.sample`: ASCII-only Docker/WSL2 및 외부 DB 템플릿
- `README.md`: Linux/WSL2 지원 범위, Docker Compose, 외부 DB, 로그, volume과 검증 절차

## 요구사항 검증 결과

| R-13 기준 | 결과 | 증거 |
| --- | --- | --- |
| Linux/OpenSCAD 이미지 정의 | Pass (정적) | `tests/test_deployment.py` |
| Compose 앱 단일 service 및 DB service 부재 | Pass (정적) | `tests/test_deployment.py` |
| 비밀정보 build context 제외 | Pass (정적) | `.dockerignore`, `tests/test_deployment.py` |
| Workspace named volume | Pass (정적) | `docker-compose.yml`, `tests/test_deployment.py` |
| Job workspace `cwd` | Pass | `tests/test_unit_3.py` |
| 서버 ERROR traceback | Pass | `tests/test_unit_5.py` |
| `.env.sample` ASCII-only | Pass | `tests/test_deployment.py` |
| 기존 API/SSE 회귀 없음 | Pass | 전체 56 tests |
| Compose config/build 및 실제 OpenSCAD smoke | N/A | 현재 환경에 Docker CLI가 설치되어 있지 않음 |

## 실행한 검증

- Unit 3: `10 passed`
- Unit 5 + deployment: `21 passed`
- 전체 회귀: `56 passed`
- Deployment 최종 재검증: `5 passed`
- Python compile: 성공
- 변경 파일 `git diff --check`: 성공

테스트 warning은 기존 Starlette/httpx deprecation과 timeout mock의 unawaited coroutine 경고이며 실패는 없다.

## Docker 검증 N/A 및 후속 명령

현재 Windows 실행 환경에서 `docker` command가 존재하지 않아 아래 검증은 수행하지 못했다.

```bash
docker compose config
docker compose build
docker compose run --rm app /usr/local/bin/openscad-headless --version
docker compose up -d
docker compose ps
```

실제 STL/PNG smoke test는 WSL2 또는 Linux Docker 환경에서 최소 `.scad` 파일을 volume에 배치한 뒤 `/usr/local/bin/openscad-headless`로 수행해야 한다.

## 기존 변경 보존

- `orchestrator/service.py`와 `tests/test_unit_5.py`의 기존 R-10 상세 오류 변경을 유지했다.
- `llm/client.py`, R-12 계획, 기존 build summary 등 관련 없는 dirty 변경을 수정하지 않았다.
- 데이터 모델, migration, API와 SSE 응답 계약은 변경하지 않았다.
