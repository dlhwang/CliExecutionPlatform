# R-14 보안 테스트 지침

## 정적 검증

```bash
.\venv\Scripts\python -m pytest tests/test_deployment.py -v
```

검증 항목:

- `.env`가 Docker build context에서 제외됨 (`.dockerignore` 검증)
- Dockerfile과 Compose에 실제 DB/LLM 비밀 값이 없음
- 비루트 UID 10001로 컨테이너 내부 애플리케이션 실행 보장
- `no-new-privileges`가 true이며 모든 capability가 제거(cap_drop: ALL)되었는지 검증
- Docker socket 및 host root mount 부재
- Compose 파일에 정의된 서비스 목록이 `db`와 `app`인지 검증
- 환경 변수 `.env.sample`이 ASCII-only인지 검증

## 격리 실행 보안 검증

```bash
.\venv\Scripts\python -m pytest tests/test_unit_3.py -v -k "traversal"
```

검증 항목:

- `/tmp` 임시 격리 실행 후 호스트의 workspace로 최종 출력 파일을 복사할 때, `../` 혹은 `/etc/` 등 workspace 상위 경로를 탈출하려는 output 경로를 차단하는지 검증 (`test_run_tool_with_traversal_output_fails`)

## Container 동적 검증

```bash
docker compose run --rm app id
docker compose config
docker image history cli-execution-platform-app
```

성공 기준:

- 컨테이너 내 프로세스의 UID/GID는 10001이다.
- Compose의 정의된 서비스는 `db`와 `app`이다.
- image history에 실제 비밀 값(API Key 등)이 없다.
- container가 Docker socket이나 host root에 접근할 수 없다.

현재 환경에는 Docker CLI가 없어 동적 보안 검증은 N/A입니다. 정적 및 격리 실행 보안 검증은 전체 pytest에 포함되어 통과했습니다.

