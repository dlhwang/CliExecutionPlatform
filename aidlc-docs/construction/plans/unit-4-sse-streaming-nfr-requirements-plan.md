# 비기능 요구사항 계획서 - Unit 4: SSE Streaming & Event Catch-up

## 목적

Unit 4 SSE 스트림 기능의 성능, 확장성, 가용성, 보안, 신뢰성 기준을 정하고 구현 단계에서 검증 가능한 비기능 요구사항과 기술 선택을 확정합니다.

## 입력 산출물

- `aidlc-docs/construction/unit-4-sse-streaming/functional-design/business-logic-model.md`
- `aidlc-docs/construction/unit-4-sse-streaming/functional-design/business-rules.md`
- `aidlc-docs/construction/unit-4-sse-streaming/functional-design/domain-entities.md`
- `jobs/models.py`
- `database.py`

## 실행 체크리스트

- [x] Step 1: Unit 4 기능 설계 산출물 분석 완료
- [x] Step 2: NFR Requirements 계획 작성 완료
- [x] Step 3: NFR 및 기술 선택 질문 작성 완료
- [x] Step 4: 사용자 답변 수집 및 모호성 검토
- [x] Step 5: NFR Requirements 산출물 작성
  - [x] `nfr-requirements.md`
  - [x] `tech-stack-decisions.md`
- [x] Step 6: 완료 메시지 제시 및 승인 대기
- [x] Step 7: 승인 기록 및 `aidlc-state.md` 진행 상태 갱신

## 설계 기준 질문

아래 질문에 대해 각 `[Answer]:` 뒤에 선택지를 기입해 주십시오.

## Question 1
Unit 4 MVP에서 동시에 유지해야 하는 SSE 연결 수 목표는 어느 수준으로 둘까요?

A) 단일 서버 기준 최대 20개 동시 연결

B) 단일 서버 기준 최대 100개 동시 연결

C) 단일 서버 기준 최대 500개 동시 연결

D) Other (please describe after [Answer]: tag below)

[Answer]: A

## Question 2
SSE 이벤트 전달 지연 목표는 어느 수준으로 둘까요?

A) 이벤트 DB 적재 후 평균 0.5초 이내 전송

B) 이벤트 DB 적재 후 평균 1초 이내 전송

C) 이벤트 DB 적재 후 평균 3초 이내 전송

D) Other (please describe after [Answer]: tag below)

[Answer]: C

## Question 3
SSE 접근 키는 MVP에서 어떻게 관리할까요?

A) 환경 변수 `SSE_STREAM_API_KEY` 기반 단일 공유 키

B) Job 생성 응답에 포함되는 Job별 임시 스트림 토큰

C) API Key 검증 구조만 만들고 개발 환경에서는 키가 없으면 허용

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 4
SSE 연결의 최대 유지 시간 또는 idle timeout은 어떻게 둘까요?

A) Job 종료 전까지 유지하되, 서버 idle timeout은 별도로 두지 않는다.

B) 최대 10분 연결 후 클라이언트 재연결을 유도한다.

C) 최대 30분 연결 후 클라이언트 재연결을 유도한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: B

## Question 5
DB polling 부하 제어는 MVP에서 어느 수준까지 포함할까요?

A) 0.5초 고정 polling과 `job_id,id` 인덱스 사용만 포함한다.

B) 0.5초 polling에 더해 연결 수 상한과 per-Job 연결 수 제한을 포함한다.

C) polling 대신 Queue/PubSub 구조를 도입한다.

D) Other (please describe after [Answer]: tag below)

[Answer]: A

결정 근거: Queue/PubSub 방식은 이벤트 생산 경로와 배포 인프라 변경이 필요합니다. 현재 목표인 단일 서버 20개 연결과 평균 3초 지연은 기존 결합 인덱스를 사용하는 0.5초 polling으로 MVP 검증이 가능하므로, 사용자가 제시한 조건에 따라 A로 확정했습니다.
