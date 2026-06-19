# 비기능 요구사항 정의서 (Non-Functional Requirements) - Unit 2: Parser & Policy Validator Service

본 문서는 **Unit 2: Parser & Policy Validator Service**의 성능 지연 기준, 보안 침투 감사 로깅 및 데이터베이스 적재 규칙, 그리고 LLM 응답 실패에 대한 복구 메커니즘을 규정합니다.

---

## 1. 비기능 품질 목표 및 임계 지표 (Quality Attributes)

### 1.1 성능 요구사항 (Performance NFR)
* **목표 지연 시간 (Latency Limit)**:
  - 입력 텍스트 내 JSON 마크다운 파싱, Pydantic DTO 매핑, 보안 위반 확인(디렉토리 Traversal, symlink 물리 검사 포함)의 모든 단계를 수행하는 데 소요되는 최대 지연 시간은 **500ms 이내**로 제한합니다. (사용자 결정: 질문 1 - 옵션 B)
  - 호스트 파일 시스템 입출력(존재 여부 조회, absolute path 확인) 및 데이터베이스 로깅을 수행하더라도 500ms를 초과하지 않도록 최적화합니다.

### 1.2 보안 및 감사 요구사항 (Security & Audit NFR)
* **침투 감사 로그 영구 적재 (Security Audit Trail)**:
  - 보안 정책 위반(예: `relative_path` 내 `../` 패턴 인입, 절대 경로 지정, 심볼릭 링크 활용, `RUN_TOOL` 내 비인가 툴 요청 등)이 감지되어 `PermissionError`가 던져질 시, 백엔드 파일 로그 기록과 더불어 데이터베이스의 `event_logs` 테이블에 관련 위반 사항을 즉시 기록합니다. (사용자 결정: 질문 2 - 옵션 A)
  - 이벤트 종류(`event_type`)는 `SECURITY_ALERT`로 등록하며, 상세 에러 내용과 함께 기록되어 프론트엔드 실시간 SSE 및 관리 콘솔에서 침투 시도를 감지할 수 있도록 보장합니다.

### 1.3 가동성 및 신뢰성 요구사항 (Availability & Reliability NFR)
* **재시도 가능 예외 아키텍처 제공 (Recoverability)**:
  - LLM이 반환한 JSON 문자열의 구문이 깨져 파싱이 불가능한 경우, 이를 즉시 `FAILED` 상태로 종료하지 않고 상위 오케스트레이터에게 복구 기회를 부여하기 위해 전용의 재시도 예외 클래스(`LLMPlanRetryableException`)를 정의하여 던집니다. (사용자 결정: 질문 3 - 옵션 A)
  - 오케스트레이터(Unit 5)는 해당 예외를 캐치하여 LLM에게 수정 프롬프트와 함께 재요청(Retry)을 수행할 수 있게 신뢰성을 지원합니다.
