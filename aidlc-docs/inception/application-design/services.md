# 서비스 오케스트레이션 정의서 (Services & Orchestration)

본 문서는 플랫폼의 핵심 비즈니스 로직 시나리오를 통제하는 서비스 레이어 및 단일 진입점인 `JobOrchestratorService`의 조정 패턴을 기술합니다.

---

## 1. Job Orchestrator Service 개요

`JobOrchestratorService`는 Job의 생성부터 LLM 계획 수립, 파일 입출력 제어, 격리된 CLI 도구 실행, 그리고 산출물 영속화에 이르는 전 과정을 조율(Orchestration)합니다. 이 서비스는 백그라운드 태스크(FastAPI BackgroundTasks)를 통해 비동기적으로 실행되어 API 응답을 블로킹하지 않습니다.

---

## 2. 오케스트레이션 상세 흐름 (Job Execution Flow)

사용자가 설계를 요청했을 때 수행되는 비동기 작업의 순차적 단계입니다.

```
[클라이언트 요청]
       |
       | 1. POST /api/v1/jobs (prompt)
       v
+--------------+     2. create_job()     +------------------+
|  API Router  | ----------------------> |    JobManager    |
+--------------+                         +------------------+
       |                                          |
       | 3. Submit Background Task                | 2.1 Job(CREATED) DB 기록
       v                                          v
+-----------------------------+          +------------------+
|   JobOrchestratorService    |          |   PostgreSQL DB  |
+-----------------------------+          +------------------+
       |
       |-- 4. initialize_workspace() ---> [StorageService]
       |
       |-- 5. update_job_status(RUNNING)
       |
       |-- 6. Request Action Plan ------> [LLM API]
       |
       |-- 7. parse_plan() -------------> [ActionPlanParser]
       |
       |-- 8. validate_plan() -----------> [SecurityPolicyValidator]
       |
       |-- 9. Execute Loop (Actions)
       |    |
       |    |-- WRITE_FILE / CREATE_DIRECTORY
       |    |-- RUN_TOOL (openscad) ----> [CLIExecutionRunner] (로그 -> DB)
       |    |-- CREATE_ARTIFACT --------> [StorageService] (URL 획득)
       |
       |-- 10. update_job_status(COMPLETED / FAILED)
       |
       |-- 11. clean_workspace() -------> [StorageService]
```

### 상세 단계 설명

1. **작업 공간 확보 (Workspace Initialization)**:
   - `StorageService.initialize_workspace(job_id)`를 호출하여 서버 호스트 디렉토리에 전용 격리 폴더 `jobs/{job_id}`를 생성합니다.
2. **실행 상태 알림 (State Transition)**:
   - `JobManager.update_job_status(job_id, RUNNING)`를 호출하여 Job 상태를 `RUNNING`으로 갱신하고, `SSEConnectionManager`를 통해 진행 시작 로그를 데이터베이스에 삽입합니다. 이 로그는 SSE 연결 상태인 클라이언트 화면에 실시간 노출됩니다.
3. **LLM 계획 수립 (Action Plan Request)**:
   - LLM API를 호출하여 민수의 요구사항 프롬프트를 전달하고 사전에 정의된 JSON Schema 형식의 Action Plan을 응답받습니다.
4. **파싱 및 보안 정책 검증 (Parsing & Security Validation)**:
   - `ActionPlanParser.parse_plan(llm_raw_response)`으로 계획을 로드하고, `SecurityPolicyValidator.validate_plan(workspace_root, plan)`을 호출하여 절대경로 사용, 상위 디렉토리 이탈(`../`), 허용되지 않은 툴 실행 등을 엄격히 검증합니다. 검증 실패 시 즉시 `SecurityValidationError` 예외를 발생시키고 10단계(실패)로 점프합니다.
5. **계획 액션 실행 (Action Execution Loop)**:
   - 파싱된 액션 배열을 루프를 돌며 순차 실행합니다.
   - **`WRITE_FILE` / `CREATE_DIRECTORY`**: 검증기가 제공한 안전한 물리 경로에 파일 및 폴더를 씁니다.
   - **`RUN_TOOL`**: `CLIExecutionRunner.run_tool(workspace_root, tool_name, args)`을 통해 OpenSCAD를 30초 한도로 격리 실행합니다. 실행 중 실시간 로그(stdout/stderr)가 수집될 때마다 즉시 `SSEConnectionManager.write_event_log()`를 호출하여 DB에 기록함으로써 SSE 클라이언트와 동기화합니다.
   - **`CREATE_ARTIFACT`**: 결과물인 png, stl을 `StorageService.store_job_artifact(job_id, file_name, file_content)`를 통해 영구 저장소에 이동시키고 다운로드 URL을 반환받아 기록합니다.
6. **최종 종료 및 정리 (Finalization & Clean-up)**:
   - 모든 액션이 정상 완료되면 Job 상태를 `COMPLETED`로 변경하고, 예외 발생 시 `FAILED` 상태 및 에러 원인을 데이터베이스에 갱신합니다.
   - `StorageService.clean_workspace(job_id)`를 호출하여 Workspace 내부의 임시 파일들을 모두 소거하고 영구 저장 처리된 Artifact만을 유지하여 호스트 저장 공간의 무분별한 낭비를 예방합니다.
