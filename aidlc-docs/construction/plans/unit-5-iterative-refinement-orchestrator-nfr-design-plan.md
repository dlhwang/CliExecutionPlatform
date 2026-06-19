# 비기능 설계 계획서 - Unit 5: Iterative Refinement Orchestrator

## 목적

승인된 Unit 5 NFR을 복원력, 동시성, HTTP 자원 관리, 크기 제한, 상태 복구, 전송 보안 패턴과 논리 컴포넌트로 구체화합니다.

## 입력 산출물

- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/functional-design/`
- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/nfr-requirements/tech-stack-decisions.md`
- Unit 1-4 구현 인터페이스

## 실행 체크리스트

- [x] Step 1: 승인된 Unit 5 NFR 분석 완료
- [x] Step 2: NFR Design 계획 작성 완료
- [x] Step 3: 패턴 및 컴포넌트 설계 질문 작성 완료
- [x] Step 4: 사용자 답변 수집 및 모호성 검토
- [x] Step 5: NFR Design 산출물 작성
  - [x] `nfr-design-patterns.md`
  - [x] `logical-components.md`
- [x] Step 6: 완료 메시지 제시 및 승인 대기
- [x] Step 7: 승인 기록 및 `aidlc-state.md` 진행 상태 갱신

## 설계 질문

아래 질문의 `[Answer]:` 뒤에 선택지를 기입해 주십시오.

## Question 1
LLM HTTP 오류 중 재시도 대상으로 분류할 범위는 무엇으로 할까요?

A) timeout/연결 오류와 HTTP 408, 429, 5xx

B) timeout/연결 오류와 모든 non-2xx 응답

C) timeout/연결 오류만 재시도하고 HTTP 오류는 즉시 실패

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
semaphore 슬롯을 기다리는 `CREATED` Job의 최대 대기 시간은 어떻게 둘까요?

A) 별도 제한 없이 슬롯이 생길 때까지 대기

B) 10분 대기 후 `FAILED`

C) 30분 대기 후 `FAILED`

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 3
`httpx.AsyncClient`의 수명은 어떻게 관리할까요?

A) FastAPI lifespan 동안 하나를 공유하고 shutdown 시 close

B) 오케스트레이션 Job마다 생성하고 종료 시 close

C) LLM 재시도 시도마다 새 client 생성

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## Question 4
상속 컨텍스트가 5MB를 초과하면 어느 시점에 처리할까요?

A) refinement API 사전 검증에서 HTTP 413을 반환하고 자식 Job을 만들지 않음

B) 자식 Job을 만든 뒤 백그라운드에서 `FAILED` 처리

C) 5MB까지만 잘라서 LLM에 전달

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## Question 5
15분 stale `RUNNING` Job의 상태와 복구 이벤트는 어떻게 원자화할까요?

A) Job별 조건부 update와 EventLog insert를 하나의 트랜잭션으로 처리

B) 전체 Job 상태를 bulk update하고 복구 이벤트는 기록하지 않음

C) Job 조회, 상태 update, 이벤트 insert를 각각 별도 commit

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## Question 6
최대 5MB LLM 응답 제한은 어떻게 적용할까요?

A) streaming 응답을 읽으며 누적 byte가 5MB를 넘으면 즉시 중단

B) `Content-Length`가 있는 응답만 사전 차단하고 없으면 전체 수신

C) 전체 응답을 메모리에 받은 뒤 크기 검사

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## Question 7
LLM endpoint의 HTTP redirect는 어떻게 처리할까요?

A) redirect를 따르지 않고 3xx를 실패 처리

B) 원래 endpoint와 동일 host의 HTTPS redirect만 허용

C) 모든 redirect를 허용

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## 범주별 검토 결과

- 복원력: Question 1, 2, 5에서 재시도, 대기, stale 복구 결정
- 확장성: Question 2에서 semaphore queue 경계 결정
- 성능: Question 3, 4, 6에서 client 재사용과 메모리 제한 결정
- 보안: Question 4, 7에서 외부 입력 및 redirect 신뢰 경계 결정
- 논리 컴포넌트: Question 3, 5, 6에서 client provider, recovery service, bounded response reader 책임 결정
