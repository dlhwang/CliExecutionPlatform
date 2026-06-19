# 비기능 요구사항 계획서 - Unit 5: Iterative Refinement Orchestrator

## 목적

LLM HTTP 호출, 백그라운드 Job 실행, 상속 컨텍스트 처리에 적용할 성능, 확장성, 보안, 신뢰성 기준과 기술 선택을 확정합니다.

## 입력 산출물

- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/functional-design/business-logic-model.md`
- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/functional-design/business-rules.md`
- `aidlc-docs/construction/unit-5-iterative-refinement-orchestrator/functional-design/domain-entities.md`
- Unit 1-4 구현 및 NFR 설계

## 실행 체크리스트

- [x] Step 1: Unit 5 기능 설계 및 기존 런타임 제약 분석 완료
- [x] Step 2: NFR Requirements 계획 작성 완료
- [x] Step 3: NFR 및 기술 선택 질문 작성 완료
- [x] Step 4: 사용자 답변 수집 및 모호성 검토
- [x] Step 5: NFR Requirements 산출물 작성
  - [x] `nfr-requirements.md`
  - [x] `tech-stack-decisions.md`
- [x] Step 6: 완료 메시지 제시 및 승인 대기
- [x] Step 7: 승인 기록 및 `aidlc-state.md` 진행 상태 갱신

## NFR 질문

아래 질문의 `[Answer]:` 뒤에 선택지를 기입해 주십시오.

## Question 1
LLM HTTP 요청 1회의 timeout은 얼마로 둘까요?

A) 30초

B) 60초

C) 120초

D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 2
단일 애플리케이션 인스턴스에서 동시에 실행할 오케스트레이션 Job 수는 몇 개로 제한할까요?

A) 1개

B) 2개

C) 5개

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 3
LLM 재시도 2회의 대기 정책은 어떻게 둘까요?

A) 각 재시도 전 고정 1초

B) 1초, 2초 지수형 backoff

C) 1초, 2초 backoff에 최대 0.5초 jitter 추가

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 4
`model.scad`와 `design-spec.md`를 합친 상속 컨텍스트의 최대 크기는 얼마로 제한할까요?

A) 256KB

B) 1MB

C) 5MB

D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 5
LLM endpoint 전송 보안 정책은 어떻게 적용할까요?

A) HTTPS만 허용하고 HTTP는 모두 거부

B) 운영은 HTTPS만 허용하고 localhost 개발 환경만 HTTP 허용

C) URL scheme 제한 없이 설정값을 신뢰

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 6
프로세스 중단으로 `RUNNING`에 남은 Job을 재시작 시 어떻게 처리할까요?

A) 애플리케이션 시작 시 모든 기존 `RUNNING` Job을 `FAILED`로 전이

B) 마지막 갱신 후 15분이 지난 `RUNNING` Job만 `FAILED`로 전이

C) 자동 복구하지 않고 운영자가 처리

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## 사전 기술 결정

- HTTP 클라이언트는 기존 의존성인 `httpx.AsyncClient`를 사용합니다.
- LLM 공급자별 차이는 `LLMClient` 인터페이스와 HTTP adapter 내부에 격리합니다.
- 동시 Job 제한은 프로세스 로컬 비동기 semaphore로 적용합니다.
- 외부 Queue, worker, cache 인프라는 MVP 범위에서 추가하지 않습니다.
- 테스트는 실제 외부 LLM 호출 없이 fake client와 mock transport를 사용합니다.
