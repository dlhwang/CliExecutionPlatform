# 기능 설계 계획서 - Unit 5: Iterative Refinement Orchestrator

## 목적

Job 생성부터 LLM 계획 생성, 보안 검증, 액션 실행, 상태 전이까지의 통합 흐름과 이전 Job 기반 반복 수정 규칙을 정의합니다.

## 입력 산출물

- `aidlc-docs/inception/application-design/unit-of-work.md`
- `aidlc-docs/inception/application-design/unit-of-work-story-map.md`
- `aidlc-docs/inception/user-stories/stories.md`
- Unit 1-4 구현 및 설계 산출물
- `jobs/`, `llm/`, `runner/`, `storage/`, `sse/` 인터페이스

## 실행 체크리스트

- [x] Step 1: Unit 5 책임, S-5 인수 기준, 기존 컴포넌트 분석 완료
- [x] Step 2: Functional Design 계획 작성 완료
- [x] Step 3: 비즈니스 로직 및 도메인 질문 작성 완료
- [x] Step 4: 사용자 답변 수집 및 모호성 검토
- [x] Step 5: Functional Design 산출물 작성
  - [x] `business-logic-model.md`
  - [x] `business-rules.md`
  - [x] `domain-entities.md`
- [x] Step 6: 완료 메시지 제시 및 승인 대기
- [x] Step 7: 승인 기록 및 `aidlc-state.md` 진행 상태 갱신

## 설계 질문

아래 질문의 `[Answer]:` 뒤에 선택지를 기입해 주십시오.

## Question 1
반복 수정 요청 API 계약은 어떻게 구성할까요?

A) 기존 `POST /api/v1/jobs` 요청에 선택적 `previous_job_id` 추가

B) 별도 `POST /api/v1/jobs/{previous_job_id}/refine` 엔드포인트 추가

C) 기존 Job에 `POST /api/v1/jobs/{job_id}/feedback`으로 직접 수정

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 2
새 Job과 이전 Job의 계보 관계를 DB에 영속화할까요?

A) `jobs.parent_job_id` nullable 자기 참조 필드로 저장

B) Job의 `action_plan` 메타데이터에만 이전 Job ID 기록

C) DB에는 저장하지 않고 실행 시에만 사용

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## Question 3
이전 완료 Job에서 새 Workspace로 복사할 파일 범위는 무엇으로 할까요?

A) `model.scad`만 복사

B) `model.scad`와 `design-spec.md` 복사

C) 이전 임시 Workspace 전체 복사

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 4
MVP의 실제 LLM 호출은 어떤 계약으로 구현할까요?

A) 환경 변수의 endpoint/API key/model을 사용하는 범용 HTTP `LLMClient`와 테스트용 fake 구현

B) 특정 공급자 SDK에 직접 결합하고 테스트에서 mock 처리

C) 이번 Unit에서는 `LLMClient` 인터페이스와 fake만 구현하고 실제 HTTP 호출은 후속 범위로 연기

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## Question 5
LLM 응답 호출 또는 JSON 파싱이 일시적으로 실패할 때 최대 재시도 횟수는 어떻게 둘까요?

A) 재시도 없이 즉시 실패

B) 최초 호출 이후 최대 2회 재시도

C) 최초 호출 이후 최대 3회 재시도

D) Other (please describe after [Answer]: tag below)

[Answer]:B

## Question 6
액션 실행 중 실패했을 때 새 Job Workspace는 어떻게 처리할까요?

A) Job을 `FAILED`로 전이하고 부분 Workspace를 진단용으로 보존

B) Job을 `FAILED`로 전이하고 새 Job의 임시 Workspace를 즉시 삭제

C) 실패 액션 이전 상태로 파일 변경을 rollback

D) Other (please describe after [Answer]: tag below)

[Answer]:A

## 확정 가능한 기본 흐름

- 새 Job 상태는 `CREATED`에서 `RUNNING`으로 전이한 뒤 성공 시 `COMPLETED`, 실패 시 `FAILED`가 됩니다.
- LLM 응답은 `ActionPlanParser`로 파싱하고 `SecurityPolicyValidator`로 전체 플랜을 선검증합니다.
- 검증된 액션은 플랜 순서대로 직렬 실행합니다.
- `CREATE_DIRECTORY`, `WRITE_FILE`, `RUN_TOOL`, `CREATE_ARTIFACT` 외 액션은 허용하지 않습니다.
- 상태 전이와 주요 단계는 `EventLog`에 기록해 Unit 4 SSE에서 전달합니다.
- 프론트엔드 컴포넌트는 Unit 5 범위에 포함되지 않습니다.
