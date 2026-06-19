# 도메인 엔티티 - Unit 5: Iterative Refinement Orchestrator

## Job 확장

기존 `Job` 엔티티에 직접 부모를 나타내는 nullable 자기 참조 필드를 추가합니다.

| 필드 | 타입 | 규칙 |
|---|---|---|
| `id` | UUID | 기존 Job 식별자 |
| `parent_job_id` | UUID 또는 null | refinement Job의 직접 부모 Job ID |
| `prompt` | string | 신규 요구사항 또는 refinement 피드백 |
| `status` | string | `CREATED`, `RUNNING`, `COMPLETED`, `FAILED` |
| `action_plan` | JSON 또는 null | 검증을 통과한 실행 플랜 |
| `created_at` | datetime | 생성 시각 |
| `updated_at` | datetime | 마지막 상태 변경 시각 |

### 관계

- Job 하나는 0개 또는 1개의 직접 부모를 가집니다.
- Job 하나는 0개 이상의 자식 refinement Job을 가질 수 있습니다.
- 부모 삭제 정책은 자식 Job 자체를 삭제하지 않도록 `SET NULL` 방식이 적합합니다.
- 계보는 직접 부모 링크를 반복 조회해 추적할 수 있습니다.

## RefinementRequest

API 입력 값이며 영속 엔티티가 아닙니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `previous_job_id` | UUID | URL 경로에서 전달되는 부모 Job ID |
| `prompt` | string | 이전 결과에 적용할 자연어 피드백 |

## InheritedDesignContext

부모 Workspace에서 읽어 자식 Job과 LLM 요청에 전달하는 런타임 값입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `parent_job_id` | UUID | 원본 Job |
| `model_scad` | string | 부모 `model.scad` UTF-8 텍스트 |
| `design_spec` | string | 부모 `design-spec.md` UTF-8 텍스트 |

원본 bytes가 UTF-8로 해석되지 않으면 상속 실패로 처리합니다.

## LLMPlanRequest

`LLMClient`에 전달되는 공급자 독립 요청 값입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `job_id` | UUID | 실행 대상 Job |
| `prompt` | string | 사용자 신규 요구사항 또는 피드백 |
| `inherited_context` | `InheritedDesignContext` 또는 null | refinement 컨텍스트 |
| `allowed_actions` | string list | 네 가지 허용 액션 |
| `retry_feedback` | string 또는 null | 이전 파싱 실패의 정제된 요약 |

## LLMPlanResponse

| 필드 | 타입 | 설명 |
|---|---|---|
| `raw_text` | string | `ActionPlanParser` 입력 원문 |
| `attempt` | integer | 1부터 시작하는 호출 시도 번호 |

원본 텍스트는 기본적으로 DB에 영속화하지 않습니다. 검증된 액션만 `Job.action_plan`에 저장합니다.

## ActionPlan

Unit 2에서 정의한 액션 목록을 재사용합니다.

| 액션 | 주요 데이터 |
|---|---|
| `CREATE_DIRECTORY` | `path` |
| `WRITE_FILE` | `path`, `content` |
| `RUN_TOOL` | `tool_name`, `args` |
| `CREATE_ARTIFACT` | `path` |

## OrchestrationContext

하나의 백그라운드 실행 동안 유지되는 런타임 값입니다.

| 필드 | 타입 | 설명 |
|---|---|---|
| `job_id` | UUID | 대상 Job |
| `parent_job_id` | UUID 또는 null | 직접 부모 |
| `prompt` | string | 사용자 입력 |
| `inherited_context` | object 또는 null | 상속 파일 내용 |
| `actions` | Action list | 파싱 및 검증된 실행 목록 |
| `current_action_index` | integer | 현재 실행 위치 |
| `attempt_count` | integer | LLM 호출 횟수 |

`OrchestrationContext`는 프로세스 메모리에만 존재하며 재시작 복구 상태로 사용하지 않습니다.

## EventLog 재사용

기존 `EventLog`는 상태 및 단계 진행을 기록합니다.

| 이벤트 유형 | 용도 |
|---|---|
| `SYSTEM_EVENT` | 상태 전이, 상속, LLM 호출, 액션 진행 |
| `CLI_OUTPUT` | Unit 3의 CLI 출력 |
| `SECURITY_ALERT` | Unit 2의 정책 위반 |

## 엔티티 불변 조건

- `parent_job_id`는 Job 생성 후 변경하지 않습니다.
- 부모와 자식 Job ID는 같을 수 없습니다.
- `COMPLETED` 부모만 refinement의 실행 컨텍스트가 될 수 있습니다.
- `action_plan`에는 전체 보안 검증을 통과한 액션만 저장합니다.
- 종료 상태 Job은 다시 실행하지 않습니다.

