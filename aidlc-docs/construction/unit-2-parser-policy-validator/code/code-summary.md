# 코드 생성 요약 (Code Summary) - Unit 2: Parser & Policy Validator Service

> 생성 완료 일시: 2026-06-19T10:47:00+09:00  
> 테스트 결과: **9/9 통과** (Unit 1 + Unit 2 회귀 테스트 포함)

---

## 생성된 파일 목록

| 파일 | 액션 | 역할 |
|------|------|------|
| [`llm/schemas.py`](file:///d:/workspace/CLI-Execution-Platform/llm/schemas.py) | 신규 생성 | Pydantic 2.x 다형성 Discriminator 스키마 (`CreateDirectoryAction`, `WriteFileAction`, `RunToolAction`, `CreateArtifactAction`, `ActionType` 유니온) |
| [`llm/parser.py`](file:///d:/workspace/CLI-Execution-Platform/llm/parser.py) | 신규 생성 | `ActionPlanParser` — Markdown JSON 추출 (코드블록 우선, Fallback `[…]` 범위 추출) + 커스텀 예외 계층 (`LLMPlanException`, `LLMPlanRetryableException`, `LLMPlanValidationError`) |
| [`llm/validator.py`](file:///d:/workspace/CLI-Execution-Platform/llm/validator.py) | 신규 생성 | `SecurityPolicyValidator` — Path Traversal / 절대경로 / Symlink / Tool Whitelist 4종 보안 검증 + `SECURITY_ALERT` 동기식 DB 감사 로그 적재 |
| [`tests/test_unit_2.py`](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_2.py) | 신규 생성 | 통합 테스트 5개 |

---

## 구현된 핵심 컴포넌트 요약

| 컴포넌트 | 핵심 메커니즘 | 구현 특이사항 |
|---------|-------------|------------|
| `ActionPlanParser` | `````json … ````` 코드블록 정규식 → JSON 파싱 → Pydantic 검증 | 코드블록 없을 시 첫 `[` ~ 마지막 `]` 범위 Fallback 추출 |
| `LLMPlanRetryableException` | JSON 구문 오류(JSONDecodeError) 포착 | `raw_content`, `error_position` (line/col) 속성 포함 |
| `LLMPlanValidationError` | Pydantic ValidationError 래핑 | `status_code=403`, `error_code="FORBIDDEN_ACCESS"` 지원 |
| `SecurityPolicyValidator` | 4단계 경로 검증 체인 | `is_relative_to()` + 경로 체인 `is_symlink()` 순회 검사 |
| DB 감사 로그 | `EventLog(event_type="SECURITY_ALERT")` 동기 INSERT | 위반 감지 즉시 DB 커밋 후 예외 발생 (원자성 보장) |

---

## 구현된 보안 검증 체계

| 검증 규칙 | 차단 조건 | 예외 |
|---------|---------|------|
| Path Traversal 방어 | `../` 또는 `..\` 포함 경로 | `LLMPlanValidationError(403)` |
| 절대경로 차단 | `/` 또는 `\` 시작 또는 `Path.is_absolute()` | `LLMPlanValidationError(403)` |
| 작업 영역 이탈 방어 | `resolve()` 후 `is_relative_to(base_dir)` 실패 | `LLMPlanValidationError(403)` |
| Symlink 탐지 | 경로 체인 상 `is_symlink()` True인 구성 요소 존재 | `LLMPlanValidationError(403)` |
| Tool Whitelist | `tool_name.lower() != "openscad"` | `LLMPlanValidationError(403)` |

---

## 요구사항 검증 결과 (Requirement Verification Evidence)

| 스토리 ID | 요구사항 | 테스트 함수 | 결과 |
|----------|---------|-----------|------|
| S-6 | Markdown JSON 추출 (코드블록 + Fallback) | `test_json_extraction_success` | ✅ PASS |
| S-6 | JSON 구문 오류 시 재시도 예외 발생 | `test_parser_retryable_exception` | ✅ PASS |
| S-6 | Pydantic 스키마 검증 실패 예외 발생 | `test_parser_validation_exception` | ✅ PASS |
| S-6 | 경로 침투/절대경로/Symlink 차단 + DB 감사 로그 | `test_security_validator_path_protection` | ✅ PASS |
| S-6 | Tool Whitelist 차단 (openscad만 허용) | `test_security_validator_tool_whitelist` | ✅ PASS |

---

## 전체 테스트 회귀 결과 (Unit 3 완료 시점 기준)

```
tests/test_unit_1.py   4/4  PASS
tests/test_unit_2.py   5/5  PASS
tests/test_unit_3.py   8/8  PASS
──────────────────────────────
합계               17/17  PASS (회귀 없음)
```

---

## N/A 항목

없음 — 모든 S-6 스토리 인수 기준이 자동화 테스트로 커버되었습니다.
