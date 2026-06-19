# 비즈니스 로직 모델 - Unit 5: Iterative Refinement Orchestrator

## 목적

Unit 5는 Job 생성 후 실행되는 백그라운드 흐름을 통합합니다. LLM 계획 생성, JSON 파싱, 보안 검증, 파일 및 CLI 액션 실행, Artifact 저장, Job 상태 전이를 하나의 순서 있는 프로세스로 관리합니다. 완료 Job을 부모로 지정한 refinement 요청은 이전 `model.scad`와 `design-spec.md`를 새 Workspace에 상속합니다.

## API 흐름

### 신규 설계 Job

1. 클라이언트가 `POST /api/v1/jobs`에 자연어 prompt를 전송합니다.
2. 서버는 `parent_job_id = null`, `status = CREATED`인 Job과 Workspace를 생성합니다.
3. 응답으로 Job ID, SSE URL, 스트림 토큰을 반환합니다.
4. 백그라운드에서 오케스트레이터를 실행합니다.

### 반복 수정 Job

1. 클라이언트가 `POST /api/v1/jobs/{previous_job_id}/refine`에 피드백 prompt를 전송합니다.
2. 서버는 이전 Job이 존재하고 `COMPLETED`인지 검증합니다.
3. 이전 Workspace에 `model.scad`와 `design-spec.md`가 모두 존재하는지 검증합니다.
4. 서버는 `parent_job_id = previous_job_id`, `status = CREATED`인 새 Job과 Workspace를 생성합니다.
5. 응답으로 새 Job ID, SSE URL, 스트림 토큰을 반환합니다.
6. 백그라운드 오케스트레이터가 두 파일을 새 Workspace로 복사하고 피드백과 함께 LLM 컨텍스트로 사용합니다.

## 오케스트레이션 흐름

1. 대상 Job을 조회하고 `CREATED` 상태인지 확인합니다.
2. Job 상태를 `RUNNING`으로 전이하고 시작 `EventLog`를 기록합니다.
3. refinement Job이면 부모 Job을 다시 검증하고 상속 파일을 읽어 새 Workspace에 기록합니다.
4. `LLMPlanRequest`를 구성합니다.
   - 신규 Job: 사용자 prompt와 플랫폼 액션 규칙
   - refinement Job: 피드백 prompt, 부모 `model.scad`, 부모 `design-spec.md`, 플랫폼 액션 규칙
5. `LLMClient`가 환경 설정된 HTTP endpoint에 요청하고 원본 텍스트 응답을 반환합니다.
6. `ActionPlanParser`가 원본 텍스트를 액션 목록으로 변환합니다.
7. HTTP 일시 오류 또는 `LLMPlanRetryableException`이면 최초 시도 이후 최대 2회 재시도합니다.
8. 파싱된 전체 액션 목록을 `SecurityPolicyValidator`로 실행 전에 선검증합니다.
9. 검증된 액션 목록을 Job의 `action_plan`에 저장합니다.
10. 액션을 목록 순서대로 하나씩 실행합니다.
11. 모든 액션이 성공하면 Job 상태를 `COMPLETED`로 전이하고 완료 이벤트를 기록합니다.
12. 어느 단계에서든 실패하면 Job 상태를 `FAILED`로 전이하고 정제된 실패 이벤트를 기록합니다. 생성된 부분 Workspace는 삭제하거나 rollback하지 않습니다.

## 액션 실행 매핑

| 액션 | 실행 동작 |
|---|---|
| `CREATE_DIRECTORY` | 새 Job Workspace 안에 상대 디렉터리 생성 |
| `WRITE_FILE` | `StorageService.write_file`로 텍스트 파일 기록 |
| `RUN_TOOL` | `CLIExecutionRunner.run_tool`로 OpenSCAD 실행 |
| `CREATE_ARTIFACT` | `StorageService.save_artifact`로 영구 Artifact 영역에 복사 |

액션은 직렬 실행합니다. 앞 액션의 파일 출력이 뒤 액션 입력이 될 수 있으므로 순서를 변경하거나 병렬화하지 않습니다.

## LLMClient 계약

`LLMClient`는 공급자별 응답 구조를 오케스트레이터에서 분리하는 포트입니다.

- 입력: model, 사용자 prompt, 선택적 상속 파일 컨텍스트, 허용 액션 규칙
- 출력: `ActionPlanParser`에 전달할 원본 텍스트
- 설정: endpoint, API key, model은 환경 설정에서 주입
- 실패: 재시도 가능한 전송/서버 오류와 재시도 불가능한 인증/요청 오류를 구분
- 테스트: 동일 인터페이스의 fake client로 결정적 응답 또는 오류를 주입

외부 HTTP payload와 응답 필드 매핑은 NFR Requirements 및 NFR Design에서 구체화합니다.

## 재시도 흐름

- 전체 호출 횟수는 최초 1회와 재시도 최대 2회를 합쳐 최대 3회입니다.
- HTTP timeout, 연결 오류, 서버의 일시 오류, JSON 구문 추출 실패만 재시도합니다.
- Pydantic 스키마 위반, 보안 정책 위반, 인증 실패는 재시도하지 않습니다.
- JSON 파싱 실패 후 재시도할 때는 파싱 오류 요약을 다음 LLM 요청에 포함할 수 있습니다.
- 각 시도와 최종 소진은 민감정보 없이 `EventLog`에 기록합니다.

## 실패 처리

- 상태 전이는 최종적으로 `FAILED`여야 합니다.
- 이미 생성된 파일과 실행 로그는 진단을 위해 보존합니다.
- 실행된 파일 변경과 Artifact를 rollback하지 않습니다.
- API key, 전체 LLM 원본 응답, 내부 경로 등 민감하거나 과도한 내용은 실패 이벤트에 기록하지 않습니다.
- 백그라운드 예외가 FastAPI 프로세스 밖으로 전파되어 Job이 `RUNNING`에 고정되지 않도록 최상위 실패 처리를 둡니다.

