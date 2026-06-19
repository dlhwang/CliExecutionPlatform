# 비기능 설계 패턴 - Unit 5: Iterative Refinement Orchestrator

## 설계 목표

Unit 5는 외부 LLM 호출과 로컬 파일/CLI 실행을 결합하므로, 외부 장애를 제한하고 메모리와 동시 실행 수를 통제하며 Job 상태를 최종 상태로 수렴시켜야 합니다.

## ND-5-1: 선택적 제한 재시도

- 전체 LLM 호출은 최초 1회와 재시도 2회를 합쳐 최대 3회입니다.
- 재시도 대상은 timeout, 연결 오류, HTTP 408, HTTP 429, HTTP 5xx, `LLMPlanRetryableException`입니다.
- HTTP 3xx, 400, 401, 403, 404 및 기타 4xx는 즉시 실패합니다. 단, 408과 429는 예외입니다.
- 재시도 전 1초, 2초를 `asyncio.sleep`으로 대기합니다.
- 매 시도는 동일한 shared HTTP client를 사용합니다.
- 최종 실패는 원래 응답 본문이나 인증 정보를 노출하지 않는 도메인 오류로 변환합니다.

## ND-5-2: 동시성 벌크헤드와 대기 timeout

- 프로세스 로컬 `asyncio.Semaphore(2)`로 실행 중 오케스트레이션을 두 개로 제한합니다.
- semaphore 대기는 `asyncio.wait_for`로 최대 10분 제한합니다.
- 슬롯 대기 중 Job은 `CREATED` 상태를 유지합니다.
- 10분 안에 슬롯을 획득하지 못하면 Job을 `FAILED`로 전이하고 `ORCHESTRATION_QUEUE_TIMEOUT` 이벤트를 기록합니다.
- 슬롯은 성공, 실패, 취소를 포함한 모든 종료 경로에서 `finally`로 반환합니다.

## ND-5-3: lifespan 공유 HTTP client

- FastAPI lifespan 시작 시 `httpx.AsyncClient` 하나를 생성하고 종료 시 `aclose`합니다.
- 120초 전체 요청 timeout과 `follow_redirects=False`를 설정합니다.
- client는 의존성 또는 app state를 통해 adapter에 전달합니다.
- API key와 endpoint 검증은 client 생성 전에 수행합니다.
- 연결 풀을 공유하되 인증 헤더나 Job별 payload를 전역 mutable 상태로 보관하지 않습니다.

## ND-5-4: 사전 컨텍스트 경계 검증

- refinement API는 자식 Job 생성 전에 부모 파일 존재 여부와 합계 크기를 검증합니다.
- `model.scad`와 `design-spec.md`의 UTF-8 byte 합계가 5MB를 초과하면 HTTP 413을 반환합니다.
- 초과 시 자식 Job, Workspace, BackgroundTask를 만들지 않습니다.
- 파일 내용을 자르지 않습니다.
- 경로 검증은 기존 `StorageService`의 Job Workspace 경계를 그대로 적용합니다.

## ND-5-5: bounded streaming 응답

- HTTP adapter는 `AsyncClient.stream`으로 응답 body를 청크 단위로 읽습니다.
- `Content-Length`가 5MB보다 크면 body를 읽기 전에 중단할 수 있지만, 이 헤더만 신뢰하지 않습니다.
- 실제 누적 수신 byte가 5MB를 초과하는 즉시 스트림을 닫고 재시도 불가능한 크기 오류를 발생시킵니다.
- 제한 안의 body만 UTF-8 및 JSON으로 디코딩합니다.
- 원본 body는 로그나 DB에 저장하지 않습니다.

## ND-5-6: redirect 거부

- HTTP client의 redirect 자동 추적을 비활성화합니다.
- 모든 3xx 응답은 재시도 불가능한 endpoint 오류로 처리합니다.
- redirect 대상 URL을 해석하거나 요청하지 않으므로 설정된 신뢰 경계를 벗어나지 않습니다.

## ND-5-7: 상태 전이 트랜잭션

- 상태 전이와 해당 `EventLog` insert를 동일 DB 세션과 트랜잭션에서 커밋합니다.
- 실행 시작은 `status == CREATED` 조건부 update로 수행해 중복 실행을 방지합니다.
- update row count가 0이면 액션을 실행하지 않습니다.
- 성공과 실패 전이도 현재 상태 조건을 포함해 종료 상태 덮어쓰기를 방지합니다.
- DB 트랜잭션 실패 시 rollback하고 새 짧은 세션에서 제한적으로 실패 상태 기록을 시도합니다.

## ND-5-8: stale Job 원자 복구

- 시작 시 `RUNNING`이면서 `updated_at < now - 15분`인 Job ID를 조회합니다.
- 각 Job에 대해 같은 조건을 포함한 update와 복구 `EventLog` insert를 하나의 트랜잭션으로 처리합니다.
- 조건부 update row count가 1일 때만 이벤트를 기록합니다.
- 다른 프로세스가 먼저 상태를 변경해 row count가 0이면 이벤트를 중복 기록하지 않습니다.
- 복구된 Job의 Workspace와 Artifact는 보존합니다.

## ND-5-9: 외부 데이터 신뢰 경계

- 설정 endpoint는 운영 HTTPS 또는 개발 loopback HTTP 규칙을 통과해야 합니다.
- LLM 응답은 크기 제한, JSON 추출, Pydantic schema, 보안 정책 순서로 검증합니다.
- 전체 플랜 검증 전에 액션을 실행하지 않습니다.
- API key, prompt 전문, 상속 파일 전문, 원본 응답 전문을 구조화 로그와 EventLog에서 제외합니다.

## ND-5-10: 테스트 가능 시간 및 I/O

- sleep, semaphore wait timeout, 현재 시각, HTTP transport를 주입 가능하게 구성합니다.
- 120초와 10분을 실제로 기다리지 않고 timeout 경로를 검증합니다.
- `httpx.MockTransport`와 fake `LLMClient`로 외부 네트워크를 사용하지 않습니다.

## 요구사항 매핑

| 요구사항 | 설계 패턴 |
|---|---|
| NFR-5-1, NFR-5-5 | ND-5-1, ND-5-3 |
| NFR-5-2 | ND-5-2 |
| NFR-5-4 | ND-5-4, ND-5-5 |
| NFR-5-6 | ND-5-7 |
| NFR-5-7 | ND-5-8 |
| NFR-5-9, NFR-5-10 | ND-5-3, ND-5-6, ND-5-9 |
| NFR-5-11 | ND-5-5, ND-5-9 |
| NFR-5-12, NFR-5-14 | ND-5-10 |

