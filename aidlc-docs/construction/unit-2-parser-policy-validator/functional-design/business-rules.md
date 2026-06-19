# 비즈니스 규칙 및 검증 규칙서 (Business Rules & Validation) - Unit 2: Parser & Policy Validator Service

본 문서는 **Unit 2: Parser & Policy Validator Service**의 JSON 파싱, CLI 실행 제한 조건, 절대경로/상대경로 탈출 및 심볼릭 링크 방어 제약 조건과 에러 발생 시 REST API 규격 매핑 정책을 규정합니다.

---

## 1. 보안 유효성 검증 제약 조건 (Validation Constraints)

플랫폼의 안전한 구동을 위해 액션 플랜이 인입되었을 때 거쳐야 하는 보안 정책 테이블입니다.

| 검증 영역 | 상세 제약 조건 (Constraint Rules) | 처리 대상 액션 | 위반 시 대응 예외 (Exception) |
| :--- | :--- | :--- | :--- |
| **상대경로 침투 차단** | `path` 문자열 내에 상위 디렉토리 이동 기호(`../`, `..\\`)가 포함되어서는 안 됩니다. | `CREATE_DIRECTORY`<br/>`WRITE_FILE`<br/>`CREATE_ARTIFACT` | `PermissionError`<br/>(FORBIDDEN_ACCESS) |
| **절대경로 차단** | `path`가 `/` 혹은 `\\`로 시작하거나 `Path(p).is_absolute()`가 참인 절대경로 명시를 차단합니다. | `CREATE_DIRECTORY`<br/>`WRITE_FILE`<br/>`CREATE_ARTIFACT` | `PermissionError`<br/>(FORBIDDEN_ACCESS) |
| **심볼릭 링크 탐색 차단** | 물리 작업 영역 하위의 타겟 경로에 이미 존재하는 파일이 심볼릭 링크(`is_symlink()`)인 경우 차단합니다. | `WRITE_FILE`<br/>`CREATE_ARTIFACT` | `PermissionError`<br/>(FORBIDDEN_ACCESS) |
| **도구 화이트리스트 검사** | `tool_name`에 명시된 툴이 `openscad` (대소문자 무시) 목록에 정확히 속하는지 검사합니다. | `RUN_TOOL` | `PermissionError`<br/>(FORBIDDEN_ACCESS) |
| **물리 영역 합치성 검증** | 액션 파일의 resolve된 물리 경로가 Job 디렉토리(`.workspaces/jobs/{job_id}/`)의 완전한 하위에 종속되는지 `is_relative_to()`로 최종 검사합니다. | `CREATE_DIRECTORY`<br/>`WRITE_FILE`<br/>`CREATE_ARTIFACT` | `PermissionError`<br/>(FORBIDDEN_ACCESS) |

---

## 2. 에러 핸들링 및 표준 REST API 매핑 정책 (Error Mapping Policy)

Unit 2 처리 도중 예외가 발생할 경우 표준 에러 응답 포맷인 `{ "detail": { "status": "error", "code": "[ERROR_CODE]", "message": "[DESCRIPTIVE_MESSAGE]" } }` 규격으로 가공되어 전달되어야 합니다.

### 2.1 예외별 상세 에러 매핑 매트릭스

1. **LLM 응답 JSON 파싱 실패 (Markdown Extraction Fail 또는 Invalid JSON 문법)**:
   * **원인**: LLM 응답에 유효한 JSON 배열이 없거나 JSON 포맷이 깨진 경우
   * **HTTP 상태 코드**: `400 Bad Request`
   * **내부 에러 코드 (`code`)**: `VALIDATION_ERROR`
   * **에러 메시지 (`message`)**: `"Failed to parse LLM response as a valid Action Plan JSON."`

2. **Pydantic 스키마 검증 실패 (필드 누락 혹은 잘못된 액션 타입 지정)**:
   * **원인**: 필수 필드(`path`, `content` 등)가 없거나 `action` 명이 유효하지 않은 경우
   * **HTTP 상태 코드**: `400 Bad Request`
   * **내부 에러 코드 (`code`)**: `VALIDATION_ERROR`
   * **에러 메시지 (`message`)**: Pydantic `ValidationError`에서 추출한 구체적인 필드 에러 메시지 세트

3. **보안 제약 조건 위반 (Directory Traversal, 절대경로 사용, 비인가 툴 기동 등)**:
   * **원인**: 1절의 보안 유효성 검증 제약 조건 중 하나라도 위반한 액션이 감지된 경우
   * **HTTP 상태 코드**: `403 Forbidden`
   * **내부 에러 코드 (`code`)**: `FORBIDDEN_ACCESS`
   * **에러 메시지 (`message`)**: `"Access denied. Security policy violation: [위반된 구체적인 내역(예: Path traversal detected / Unauthorized tool)]"`
