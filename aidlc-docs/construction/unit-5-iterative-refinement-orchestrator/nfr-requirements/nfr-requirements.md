# 비기능 요구사항 - Unit 5: Iterative Refinement Orchestrator

## 범위

Unit 5의 LLM HTTP 호출, 백그라운드 오케스트레이션, refinement 컨텍스트, 상태 복구에 적용할 성능, 확장성, 보안, 신뢰성 및 유지보수성 기준을 정의합니다.

## 성능 및 확장성

### NFR-5-1: LLM 요청 timeout

- LLM HTTP 요청 1회의 전체 timeout은 120초입니다.
- DNS, 연결, 요청 전송, 응답 수신을 포함한 단일 시도 전체에 timeout을 적용해야 합니다.
- timeout은 재시도 가능한 오류로 분류합니다.

### NFR-5-2: 동시 오케스트레이션

- 단일 애플리케이션 프로세스에서 동시에 실행 가능한 오케스트레이션 Job은 최대 2개입니다.
- 제한은 프로세스 로컬 비동기 semaphore로 적용합니다.
- 세 번째 이후 Job은 실패시키지 않고 semaphore 획득을 대기하며 상태는 `CREATED`로 유지합니다.
- 여러 worker를 실행하면 제한은 worker별로 적용되며 전역 분산 제한은 MVP 범위에서 제외합니다.

### NFR-5-3: API 응답성

- Job 생성 및 refinement 접수 API는 외부 LLM 완료를 기다리지 않아야 합니다.
- 정상적인 로컬 DB와 파일시스템 환경에서 접수 API의 p95 응답 시간은 2초 이내를 목표로 합니다.
- LLM 호출과 액션 실행은 응답 반환 후 백그라운드에서 수행합니다.

### NFR-5-4: 컨텍스트 크기

- `model.scad`와 `design-spec.md`의 UTF-8 byte 합계는 최대 5MB입니다.
- 제한을 초과한 refinement 요청은 LLM 호출 전에 거부해야 합니다.
- 파일은 전체를 중복 복사하는 임시 버퍼를 불필요하게 만들지 않도록 한 번만 읽고 크기를 검증해야 합니다.
- LLM 원본 텍스트 응답도 최대 5MB로 제한해 비정상 응답에 따른 메모리 고갈을 방지합니다.

## 신뢰성 및 가용성

### NFR-5-5: 제한된 재시도

- LLM 호출 또는 재시도 가능한 JSON 파싱 실패는 최초 시도 후 최대 2회 재시도합니다.
- 재시도 전 대기 시간은 1초, 2초입니다.
- 비동기 sleep을 사용하며 worker thread나 이벤트 루프를 차단하면 안 됩니다.
- 인증 실패, 요청 검증 실패, 보안 정책 위반, 액션 실행 실패는 재시도하지 않습니다.

### NFR-5-6: 상태 일관성

- 각 Job 상태 전이와 대응 `EventLog` 기록은 가능한 한 동일 DB 트랜잭션에서 커밋해야 합니다.
- 최상위 오케스트레이터는 모든 예외를 포착해 Job을 `FAILED`로 전이해야 합니다.
- 종료 상태인 `COMPLETED`, `FAILED`는 다시 변경하면 안 됩니다.
- 중복 실행 요청은 이미 `RUNNING` 또는 종료 상태인 Job의 액션을 재실행하면 안 됩니다.

### NFR-5-7: stale Job 복구

- 애플리케이션 시작 시 `RUNNING`이고 `updated_at`이 현재 시각보다 15분 이상 오래된 Job을 조회해야 합니다.
- 해당 Job을 `FAILED`로 전이하고 프로세스 중단 복구 이벤트를 기록해야 합니다.
- 15분 미만의 `RUNNING` Job은 변경하지 않습니다.
- MVP에서는 중단 지점부터 액션 실행을 재개하지 않습니다.

### NFR-5-8: 진단 자료 보존

- 실패 Job의 부분 Workspace, EventLog, 이미 저장된 Artifact는 자동 삭제하지 않습니다.
- 보존 정책에 따른 정리 작업은 Unit 5 범위 밖의 운영 기능으로 둡니다.

## 보안

### NFR-5-9: endpoint scheme

- 운영 환경의 LLM endpoint는 HTTPS만 허용합니다.
- 개발 및 테스트 환경에서는 host가 `localhost`, `127.0.0.1`, `::1`인 경우에만 HTTP를 허용합니다.
- URL scheme과 host는 애플리케이션 설정 로드 시 검증해야 합니다.
- 사용자 요청으로 endpoint를 변경할 수 없어야 합니다.

### NFR-5-10: 자격 증명 관리

- LLM API key는 환경 변수에서만 읽고 DB, Job action plan, EventLog, 오류 응답에 저장하지 않습니다.
- HTTP 인증 헤더와 API key는 로그에서 완전히 제외해야 합니다.
- 운영 환경에서 endpoint, API key, model 중 필수 설정이 누락되면 LLM 기능 초기화에 실패해야 합니다.

### NFR-5-11: 외부 응답 신뢰 경계

- LLM 응답은 신뢰하지 않고 기존 `ActionPlanParser`와 `SecurityPolicyValidator`를 모두 통과한 뒤 실행해야 합니다.
- 전체 플랜 선검증 전에는 파일 생성이나 CLI 실행을 시작하면 안 됩니다.
- 외부 오류 본문 전체를 클라이언트 또는 EventLog에 전달하면 안 됩니다.

## 유지보수성 및 관측성

### NFR-5-12: 컴포넌트 분리

- 오케스트레이터는 `LLMClient`, parser, validator, runner, storage를 생성자 또는 의존성으로 주입받아야 합니다.
- 실제 HTTP client와 fake client는 동일 인터페이스를 구현해야 합니다.
- LLM 공급자별 payload 및 응답 변환은 HTTP adapter 내부에 격리해야 합니다.

### NFR-5-13: 구조화 이벤트

- Job ID, 부모 Job ID, 단계, 시도 횟수, 액션 인덱스, 결과를 구조화해 기록해야 합니다.
- prompt 전문, 상속 파일 전문, LLM 원본 전문, API key는 로그에 포함하지 않습니다.
- 실패 이벤트는 안정적인 오류 코드와 정제된 메시지를 포함해야 합니다.

### NFR-5-14: 필수 자동화 테스트

- semaphore 최대 동시 실행 2개와 대기 Job 검증
- LLM 120초 timeout 및 1초, 2초 재시도 검증
- 재시도 가능/불가능 오류 분류 검증
- 5MB 컨텍스트 및 응답 크기 경계 검증
- 운영 HTTPS와 localhost HTTP 예외 검증
- 15분 stale `RUNNING` Job 복구 검증
- 상태 전이, 중복 실행 방지, 실패 Workspace 보존 검증
- 실제 네트워크 없이 fake client와 `httpx.MockTransport`를 사용하는 계약 테스트

## 사용성

- refinement 검증 실패는 HTTP 404, 409, 413 등 원인을 구분할 수 있는 상태코드와 안정적인 오류 코드를 반환해야 합니다.
- 비동기 처리 진행과 실패 결과는 Unit 4 SSE 이벤트를 통해 확인할 수 있어야 합니다.

## 범위 제외

- 외부 Queue 또는 별도 worker 프로세스
- 다중 프로세스 간 전역 동시 실행 제한
- 중단 지점부터의 액션 재개
- Workspace 자동 보존 기간 및 정리 정책
- 사용자 계정 기반 Job 소유권 검증

