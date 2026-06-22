# Hotfix R-13 Infrastructure Design 계획

## 목적

승인된 R-13 NFR Design을 WSL2/Linux Docker Engine에서 실행 가능한 Dockerfile, Docker Compose, volume, 외부 DB 및 관측성 인프라 명세로 매핑한다.

## 실행 체크리스트

- [x] R-13 NFR Design의 논리 컴포넌트와 제약을 검토한다.
- [x] 배포 환경을 WSL2 또는 Linux Docker Engine으로 확정한다.
- [x] Python/OpenSCAD/headless runtime 이미지 구성을 확정한다.
- [x] Compose 앱 단일 서비스의 compute, port, healthcheck와 restart 정책을 정의한다.
- [x] named volume과 외부 DB 네트워크 경계를 정의한다.
- [x] 비루트 사용자, capability 제거와 비밀정보 주입 방식을 정의한다.
- [x] 로그와 smoke test 관측 지점을 정의한다.
- [x] 인프라 설계 및 배포 아키텍처 문서를 작성한다.

## 질문 범주 평가

- **배포 환경**: 사용자가 WSL2 로컬 실행과 Docker Compose 배포를 명시해 추가 선택이 필요 없다.
- **Compute**: MVP 단일 replica와 단일 Uvicorn worker로 승인되어 추가 질문이 필요 없다.
- **Storage**: 기존 외부 DB와 named workspace volume으로 확정되어 추가 질문이 필요 없다.
- **Messaging**: 별도 queue를 사용하지 않는 기존 background task 구조를 유지하므로 해당 없음이다.
- **Networking**: 호스트 포트 8000과 외부 DB outbound 연결만 필요해 load balancer/API gateway 선택은 범위 밖이다.
- **Monitoring**: stdout/stderr와 Docker Compose healthcheck로 확정되어 외부 관측 플랫폼은 범위 밖이다.
- **Shared Infrastructure**: 외부 DB는 기존 자원이며 이 계획이 생성·변경하지 않으므로 별도 shared infrastructure 산출물은 만들지 않는다.

## 완료 상태

모든 계획 항목을 완료했으며 Infrastructure Design 산출물 승인 대기 상태다.
