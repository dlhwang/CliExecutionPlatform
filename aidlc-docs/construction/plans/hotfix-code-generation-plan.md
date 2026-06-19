# 코드 생성 계획서 - Hotfix (Timezone & OpenAI Client)

본 계획서는 로컬 데이터베이스의 한국 표준시(KST) 타임존 설정(R-8) 및 OpenAI 호환 Chat Completions API 페이로드 지원(R-9)을 위한 코드 수정 및 테스트 추가 절차를 정의합니다.

## 유닛 컨텍스트
- **대상 애플리케이션 파일**: `database.py`, `llm/client.py`
- **대상 테스트 파일**: `tests/test_unit_5.py`
- **선행 조건**: 실행 계획서(Workflow Planning) 승인 완료

## 요구사항 검증 매핑
- **R-8 (로컬 DB 타임존 설정)**: SQLite 테스트 환경 정상 작동 확인, PostgreSQL 연결 시 타임존 옵션 적용 검증
- **R-9 (OpenAI 호환 페이로드)**: `test_llm_client_openai_format` 신규 테스트 추가 및 통과

---

## Part 1: 계획 수립
- [x] P1: 실행 계획에 따른 작업 범위 정의 및 검토 완료
- [x] P2: `database.py` 및 `llm/client.py` 기존 코드 구조 분석 완료
- [x] P3: 검증을 위한 테스트 시나리오 정의 완료

---

## Part 2: 코드 생성 단계

### Step 1: DB 커넥션 타임존 설정 (`database.py` 수정)
- [x] `database.py`에서 `DATABASE_URL`을 파싱하여 `postgresql`로 시작하는 경우 `connect_args={"options": "-c timezone=Asia/Seoul"}`를 적용하도록 수정합니다.
- [x] SQLite(또는 기타 비-PostgreSQL) 환경에서는 해당 옵션이 전송되지 않도록 하위 호환성을 유지합니다.
- [x] **대상 파일**: [database.py](file:///d:/workspace/CLI-Execution-Platform/database.py) [MODIFY]
- [x] **스토리/요구사항**: R-8

### Step 2: LLM 클라이언트 OpenAI 호환성 확장 (`llm/client.py` 수정)
- [x] `HttpLLMClient.generate_plan` 메소드 내에서 `self._endpoint`에 `"chat/completions"`가 포함된 경우 표준 OpenAI 형식의 payload (`messages` 배열)를 전송하도록 분기 처리를 작성합니다.
- [x] 응답 파싱 시, OpenAI API 응답 형식(`choices[0].message.content`)을 감지하여 텍스트를 추출하며, 그렇지 않은 경우에는 기존의 `content` 키에서 추출하는 폴백 메커니즘을 적용합니다.
- [x] **대상 파일**: [llm/client.py](file:///d:/workspace/CLI-Execution-Platform/llm/client.py) [MODIFY]
- [x] **스토리/요구사항**: R-9, NFR-5-4

### Step 3: LLM 클라이언트 OpenAI 호환성 검증 테스트 추가 (`tests/test_unit_5.py` 수정)
- [x] `tests/test_unit_5.py`에 `test_llm_client_openai_format` 비동기 테스트 케이스를 추가하여 `chat/completions` 주소가 포함된 endpoint 호출 시 올바른 OpenAI 형식의 payload를 빌드하여 전송하고, 응답 형식을 알맞게 파싱해오는지 검증합니다.
- [x] **대상 파일**: [tests/test_unit_5.py](file:///d:/workspace/CLI-Execution-Platform/tests/test_unit_5.py) [MODIFY]
- [x] **스토리/요구사항**: R-9

### Step 4: 코드 생성 결과 요약 및 검토 (`hotfix-code-summary.md` 생성)
- [x] `aidlc-docs/construction/hotfix/code/hotfix-code-summary.md` 문서를 생성하여 수정 사항과 테스트 결과의 요약 내용을 기록합니다.
- [x] **대상 파일**: `aidlc-docs/construction/hotfix/code/hotfix-code-summary.md` [NEW]
- [x] **스토리/요구사항**: R-8, R-9

