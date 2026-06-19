# 작업 단위별 스토리 매핑 (Unit of Work Story Mapping)

본 문서는 플랫폼의 핵심 요구사항(Requirements) 및 사용자 스토리(User Stories)가 각 개발 단위(Unit of Work)에 어떻게 분배되어 매핑되는지 기술하여, 구현(CONSTRUCTION) 단계에서 추적성을 보장합니다.

---

## 1. 요구사항 및 스토리 매핑 테이블 (Story Mapping Table)

| 개발 작업 단위 (Unit of Work) | 매핑된 요구사항 (Requirements) | 매핑된 사용자 스토리 (User Stories) | 검증 기대 결과 (Verification Expectations) |
| :--- | :--- | :--- | :--- |
| **Unit 1: API Core & Storage Service** | - **R-1**: Job & Workspace 관리<br/>- **R-5**: Artifact 스토리지 | - **S-1**: 자연어 기반 설계 Job 요청<br/>- **S-4**: Artifact 미리보기 및 다운로드 | - API POST `/api/v1/jobs` 호출 시 Job ID 발급 및 `jobs/{job_id}` 디렉토리 생성 확인<br/>- API GET `/api/v1/artifacts/...` 다운로드 성공 및 상위 경로 침범 시 403 차단 |
| **Unit 2: LLM Plan Parser & Validator** | - **R-2**: LLM JSON Plan 검증 | - **S-6**: LLM Action Plan 파싱 및 유효성 검증 | - Pydantic JSON 파싱 성공 확인<br/>- `../`이 포함되거나 허용되지 않은 툴명이 들어간 plan 유입 시 예외 발생 검증 |
| **Unit 3: CLI Execution Runner** | - **R-3**: OpenSCAD CLI 격리 | - **S-7**: CLI 실행 격리 | - OpenSCAD subprocess 호출 시 인수 배열 처리 검증<br/>- 30초 초과 시 프로세스 강제 종료 및 리소스 반환 확인 |
| **Unit 4: SSE Streaming & Event Catch-up** | - **R-4**: SSE 및 Last-Event-ID 복구 | - **S-2**: 실시간 진행 및 로그 모니터링<br/>- **S-3**: SSE 스트림 무중단 자동 복구 | - SSE `/stream` 연결 시 0.5초 간격의 DB 로그 스트리밍 확인<br/>- `Last-Event-ID` 헤더를 포함해 요청 시 DB에서 누락 로그만 재송신(Catch-up)되는지 검증 |
| **Unit 5: Iterative Refinement Orchestrator** | - (상위 통합 레이어) | - **S-5**: 대화형 피드백을 통한 설계 반복 수정 | - API 비동기 흐름 오케스트레이션 검증<br/>- 피드백 요청 시 이전 Workspace의 `model.scad` 파일을 복사하여 새 Job Workspace에 제공하는지 검증 |

---

## 2. 추적성 보장 전략 (Traceability Strategy)

- **개발 체크리스트(task.md) 연계**: 구현 단계 진입 시 각 Unit의 코드가 생성될 때마다 매핑된 Requirements 및 User Stories의 인수 기준(Acceptance Criteria)이 반영되었는지 개별 Mark합니다.
- **테스트 커버리지 매핑**: `Build and Test` 단계에서 생성되는 `unit-test-instructions.md` 및 `integration-test-instructions.md` 문서에는 각 테스트 파일이 어떤 요구사항/스토리 ID(R-1~5, S-1~7)를 테스트하는지 상호 참조 링크를 기입하여 완전성을 입증합니다.
