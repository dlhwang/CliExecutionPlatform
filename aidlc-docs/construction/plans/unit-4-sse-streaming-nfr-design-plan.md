# 비기능 설계 계획서 - Unit 4: SSE Streaming & Event Catch-up

## 목적

승인된 Unit 4 비기능 요구사항을 복원력, 확장성, 성능, 보안 및 논리 컴포넌트 설계로 구체화합니다.

## 입력 산출물

- `aidlc-docs/construction/unit-4-sse-streaming/functional-design/`
- `aidlc-docs/construction/unit-4-sse-streaming/nfr-requirements/nfr-requirements.md`
- `aidlc-docs/construction/unit-4-sse-streaming/nfr-requirements/tech-stack-decisions.md`
- `database.py`
- `jobs/models.py`

## 실행 체크리스트

- [x] Step 1: 승인된 NFR Requirements 분석 완료
- [x] Step 2: NFR Design 계획 작성 완료
- [x] Step 3: 설계 선택 질문 작성 완료
- [x] Step 4: 사용자 답변 수집 및 모호성 검토
- [x] Step 5: NFR Design 산출물 작성
  - [x] `nfr-design-patterns.md`
  - [x] `logical-components.md`
- [x] Step 6: 완료 메시지 제시 및 승인 대기
- [x] Step 7: 승인 기록 및 `aidlc-state.md` 진행 상태 갱신

## 설계 질문

아래 질문의 `[Answer]:` 뒤에 선택지를 기입해 주십시오.

## Question 1
polling 중 일시적인 DB 오류가 발생할 때 복원력 패턴은 어떻게 적용할까요?

A) 오류 이벤트를 보내고 즉시 연결 종료

B) 0.5초, 1초, 2초 간격으로 최대 3회 재시도 후 종료

C) 연결이 종료될 때까지 무제한 재시도

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 2
한 번의 이벤트 조회 배치 상한은 몇 건으로 둘까요?

A) 100건

B) 500건

C) 1,000건

D) Other (please describe after [Answer]: tag below)

[Answer]: A) 100건

## Question 3
20개 연결 상한 외에 동일 Job의 연결 수도 제한할까요?

A) 전역 20개만 제한하고 Job별 제한은 두지 않음

B) 전역 20개, Job별 최대 5개

C) 전역 20개, Job별 최대 10개

D) Other (please describe after [Answer]: tag below)

[Answer]:A) 전역 20개만 제한하고 Job별 제한은 두지 않음

## Question 4
Job별 스트림 토큰을 전달할 전용 헤더 이름은 무엇으로 할까요?

A) `X-Stream-Token`

B) `Authorization: Bearer <token>`

C) `X-API-Key`

D) Other (please describe after [Answer]: tag below)

[Answer]:A) `X-Stream-Token`

## Question 5
동기 SQLAlchemy 조회가 async SSE 루프를 차단하지 않도록 어떤 방식을 적용할까요?

A) FastAPI/Starlette threadpool에서 polling 조회 함수 실행

B) SQLAlchemy async engine과 async DB 드라이버로 전환

C) 동기 조회를 async generator 안에서 직접 실행

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## 범주별 검토 결과

- 복원력: Question 1에서 DB 일시 장애의 재시도와 종료 정책 결정
- 확장성: Question 3에서 전역 및 Job별 연결 경계 결정
- 성능: Question 2에서 catch-up 배치 크기 결정
- 보안: Question 4에서 토큰 전달 계약 결정
- 논리 컴포넌트: Question 5에서 동기 DB와 async 스트림의 통합 패턴 결정
