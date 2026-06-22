# Hotfix R-13 NFR Design 계획

## 목적

승인된 R-13 비기능 요구사항을 Docker Compose, Linux CLI 실행, 영속성, 보안 및 관측성 설계 패턴과 논리 컴포넌트로 구체화한다.

## 실행 체크리스트

- [x] R-13 NFR Requirements와 기술 스택 결정을 검토한다.
- [x] 복원력 패턴을 평가하고 외부 DB 실패 및 컨테이너 재시작 경계를 정의한다.
- [x] 확장성 패턴을 평가하고 단일 replica 제약을 명시한다.
- [x] 성능 패턴을 평가하고 비동기 subprocess, timeout, 동시성 제한을 유지한다.
- [x] 보안 패턴을 평가하고 비루트 실행, 비밀정보 주입, 경로 격리를 설계한다.
- [x] 논리 컴포넌트를 Docker/Compose, Runner, Orchestrator 및 외부 DB 경계로 매핑한다.
- [x] NFR 설계 패턴 문서를 작성한다.
- [x] 논리 컴포넌트 문서를 작성한다.

## 질문 범주 평가

- **복원력**: 기존 30초 timeout, launch retry, 외부 DB 실패 시 fail-fast, named volume 정책으로 확정되어 추가 질문이 필요 없다.
- **확장성**: 사용자가 MVP 제약을 허용했고 단일 replica로 명시되어 추가 질문이 필요 없다.
- **성능**: 동시 CLI 2개와 비동기 subprocess가 기존 승인 사항이므로 추가 질문이 필요 없다.
- **보안**: 비밀정보 런타임 주입, 비루트 실행, shell 미사용과 workspace 격리로 확정되어 추가 질문이 필요 없다.
- **논리 컴포넌트**: 앱 단일 Compose 서비스와 외부 DB 경계가 명시되어 추가 인프라 컴포넌트 선택이 필요 없다.

## 완료 상태

모든 계획 항목을 완료했으며 NFR Design 산출물 승인 대기 상태다.
