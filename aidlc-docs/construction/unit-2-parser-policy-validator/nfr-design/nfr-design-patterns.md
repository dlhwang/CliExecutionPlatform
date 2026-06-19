# 비기능 디자인 패턴 설계서 (Non-Functional Design Patterns) - Unit 2: Parser & Policy Validator Service

본 문서는 **Unit 2: Parser & Policy Validator Service**에서 수립된 비기능 요구사항을 구현 수준의 상세 아키텍처 패턴으로 투영하기 위한 비기능 디자인 패턴 설계 명세서입니다.

---

## 1. 적용 비기능 아키텍처 패턴 (Design Patterns)

### 1.1 감사 추적 (Audit Trail) 패턴
* **목적**: 보안 위반 사항 발생 시 감사 정보 유실을 원천 방어하여 침투 감사 무결성을 보장합니다.
* **구현 방식**: 
  - `SecurityPolicyValidator`에서 보안 제약 위반(Directory Traversal 시도 등)이 감지되어 `PermissionError`를 던지기 직전에, 데이터베이스 세션을 확보하여 `event_logs` 테이블에 동기식(`db.add()`, `db.commit()`)으로 `SECURITY_ALERT` 타입의 이벤트 로그를 즉시 적재합니다. (사용자 결정: 질문 2 - 옵션 A)
  - 트랜잭션이 성공적으로 완결된 이후에 비로소 403 HTTP 예외 응답을 생성하여 반환합니다.

### 1.2 자가 치유 피드백 루프 (Self-Healing Feedback Loop) 패턴
* **목적**: LLM의 일시적 JSON 구문 오류 시 스스로 문제를 해결하여 최종적인 태스크 가동률을 극대화합니다.
* **구현 방식**:
  - `ActionPlanParser` 내부에서 `json.JSONDecodeError`가 발생한 경우, 이를 단순히 상위 컨트롤러로 전달하지 않고, `LLMPlanRetryableException`으로 감쌉니다.
  - 이 예외 객체 내부에 `error_message`(에러 상세 정보), `raw_content`(LLM이 출력했던 원본 텍스트), `error_position`(에러가 발생한 라인 번호 혹은 캐릭터 위치)을 캡슐화하여 오케스트레이터로 전달합니다. (사용자 결정: 질문 3 - 옵션 A)
  - 이를 통해 오케스트레이터(Unit 5)는 "몇 번째 줄 부근에 괄호 누락이나 문법 오류가 있습니다. 다시 작성하십시오" 라는 상세 피드백 프롬프트를 조립하여 LLM API에 교정 요청(Retry)을 보낼 수 있습니다.

### 1.3 즉시 실패 (Fail-Fast) 패턴
* **목적**: 복구 불가능한 악의적인 침투 시도나 규격 미달 액션 유입 시, 불필요한 서버 자원(LLM API 비용 등)을 낭비하지 않고 즉각 차단합니다.
* **구현 방식**:
  - Path Traversal, 심볼릭 링크 사용, 혹은 화이트리스트 이외의 툴명(`openscad` 이외)이 인입된 경우는 단순 구문 실수가 아닌 보안 침투 혹은 심각한 정책 오류로 판정합니다.
  - 이 경우 재시도 예외가 아닌 `LLMPlanValidationError` 예외를 발생시키고 즉시 전체 Job 상태를 `FAILED`로 마감 처리하여 오케스트레이터가 더 이상의 LLM 재시도 루프를 수행하지 못하도록 원천 차단합니다.

---

## 2. 예외 계층 구조 (Exception Hierarchy)

Unit 2에서 설계되어 구현에 반영될 예외 클래스 구조입니다.

```text
Exception (Base Python Exception)
 ├── LLMPlanException (Base Custom Exception)
 │    ├── LLMPlanRetryableException (재시도 루프 허용: 구문 디코딩 에러, JSONDecodeError)
 │    │    └── 속성: message, raw_content, error_position
 │    │
 │    └── LLMPlanValidationError (즉시 실패: Pydantic 필드 검증 에러, 화이트리스트/경로 보안 정책 위반)
 │         └── 속성: message, status_code (예: 400 또는 403)
```
