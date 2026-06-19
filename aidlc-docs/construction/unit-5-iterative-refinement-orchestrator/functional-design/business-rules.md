# 비즈니스 규칙 - Unit 5: Iterative Refinement Orchestrator

## BR-5-1: refinement API

반복 수정은 `POST /api/v1/jobs/{previous_job_id}/refine`으로 요청합니다. 요청 본문은 새 Job의 피드백 prompt를 포함하며 기존 Job을 직접 변경하지 않습니다.

## BR-5-2: 새 Job 생성 원칙

모든 refinement 요청은 새로운 Job과 Workspace를 생성합니다. 부모 Job의 상태, action plan, Workspace, Artifact는 변경하지 않습니다.

## BR-5-3: 부모 Job 조건

- 부모 Job이 없으면 HTTP 404를 반환합니다.
- 부모 Job 상태가 `COMPLETED`가 아니면 HTTP 409를 반환합니다.
- 자기 자신이나 아직 생성되지 않은 Job을 부모로 지정할 수 없습니다.

## BR-5-4: 계보 영속화

refinement Job은 `jobs.parent_job_id`에 직접 부모 Job ID를 저장합니다. 신규 설계 Job의 `parent_job_id`는 null입니다. 한 Job은 최대 하나의 직접 부모를 가지며 한 부모는 여러 자식 Job을 가질 수 있습니다.

## BR-5-5: 상속 파일

refinement Job은 부모 Workspace의 다음 파일만 상속합니다.

- `model.scad`
- `design-spec.md`

둘 중 하나라도 없으면 refinement 실행을 시작하지 않고 새 Job을 `FAILED`로 전이합니다. 부모 Workspace 전체나 기존 Artifact는 복사하지 않습니다.

## BR-5-6: 상속 데이터 불변성

복사는 부모 파일을 읽어 자식 Workspace에 새 파일로 기록하는 방식입니다. 자식 Job의 후속 액션은 자식 복사본만 변경할 수 있으며 부모 파일은 읽기 전용으로 취급합니다.

## BR-5-7: 상태 전이

허용 상태 전이는 다음과 같습니다.

- `CREATED`에서 `RUNNING`
- `RUNNING`에서 `COMPLETED`
- `CREATED` 또는 `RUNNING`에서 `FAILED`

종료 상태인 `COMPLETED`, `FAILED`에서 다른 상태로 되돌리지 않습니다.

## BR-5-8: LLM 호출 계약

오케스트레이터는 구체적인 공급자 SDK가 아니라 `LLMClient` 인터페이스에 의존합니다. 실제 구현은 환경 변수의 endpoint, API key, model을 사용해 HTTP 요청을 수행하고 원본 텍스트 응답을 반환합니다.

## BR-5-9: LLM 재시도

- 최초 호출 이후 최대 2회 재시도합니다.
- 전송 오류, timeout, 재시도 가능 서버 오류, `LLMPlanRetryableException`만 재시도합니다.
- 인증 실패, 요청 형식 오류, `LLMPlanValidationError`, 보안 정책 위반은 즉시 실패합니다.
- 모든 시도가 실패하면 Job을 `FAILED`로 전이합니다.

## BR-5-10: 전체 플랜 선검증

어떤 액션도 실행하기 전에 액션 목록 전체를 `SecurityPolicyValidator`로 검증해야 합니다. 한 액션이라도 위반하면 전체 실행을 시작하지 않습니다.

## BR-5-11: 액션 순서

검증된 액션은 LLM 응답에 정의된 순서대로 직렬 실행합니다. 실패한 액션 이후의 액션은 실행하지 않습니다.

## BR-5-12: 액션별 경계

- 파일과 디렉터리 경로는 항상 자식 Job Workspace 기준 상대경로입니다.
- 실행 가능한 도구는 기존 정책에 따라 OpenSCAD만 허용합니다.
- `CREATE_ARTIFACT`는 Workspace에 실제 존재하는 파일만 저장할 수 있습니다.
- 알 수 없는 액션 타입은 파싱 단계에서 거부합니다.

## BR-5-13: 상태 및 이벤트 기록

오케스트레이터는 최소한 다음 이벤트를 저장합니다.

- 실행 시작
- 부모 파일 상속 완료 또는 실패
- LLM 호출 시도 및 재시도
- 플랜 검증 완료
- 각 액션 시작 및 성공 또는 실패
- Job 완료 또는 실패

이벤트는 Unit 4 SSE가 그대로 전달할 수 있도록 Job ID와 순서를 보존합니다.

## BR-5-14: 실패 Workspace 보존

오케스트레이션 실패 시 자식 Job의 부분 Workspace와 이미 저장된 Artifact를 자동 삭제하지 않습니다. 실패 원인 분석과 재현을 위해 보존하며 자동 rollback도 수행하지 않습니다.

## BR-5-15: 오류 정보 제한

클라이언트와 EventLog에는 안정적인 오류 코드와 정제된 메시지만 기록합니다. LLM API key, 인증 헤더, 전체 외부 응답, 호스트 절대경로는 노출하지 않습니다.

## BR-5-16: 중복 실행 방지

오케스트레이터는 `CREATED` 상태 Job만 실행을 시작할 수 있습니다. 이미 `RUNNING` 또는 종료 상태인 Job에 대한 중복 백그라운드 실행 요청은 액션을 다시 실행하지 않습니다.

