#!/bin/sh
# docker/entrypoint.sh
#
# 컨테이너는 root로 시작 → bind mount 디렉토리를 appuser 소유로 chown → appuser로 exec
# 이렇게 해야 호스트에서 bind mount된 .workspaces 에 컨테이너가 쓰기 가능해집니다.
#
# docker-compose.yml에서 'user:' 지시문을 제거하고 이 스크립트가 권한 전환을 담당합니다.

set -e

WORKSPACES_DIR="/app/.workspaces"
APP_UID=10001
APP_GID=10001

# bind mount 디렉토리 소유자를 appuser로 변경 (실패해도 무시 - 777 등 이미 쓰기 가능한 경우 대응)
if [ -d "$WORKSPACES_DIR" ]; then
    chown "$APP_UID:$APP_GID" "$WORKSPACES_DIR" || true
fi

# appuser 권한으로 원래 CMD를 실행
exec gosu "$APP_UID" "$@"
