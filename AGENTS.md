# AGENTS.md

이 프로젝트에서 작동하는 모든 AI 에이전트는 작업을 시작하기 전과 수행하는 도중에 다음 지침을 반드시 준수해야 합니다.

1. **최우선 필수 지침**:
   - 작업을 진행하기 전에 항상 `aidlc-rules/core-workflow.md` 파일을 가장 먼저 읽고 그 안에 정의된 AI-DLC(AI Software Development Lifecycle) 워크플로우 규칙을 완전히 숙지하고 준수해야 합니다.
   
2. **워크플로우 단계별 준수**:
   - `core-workflow.md`에 명시된 단계(Workspace Detection, Requirements Analysis, Workflow Planning 등)를 순차적으로 밟아가며 진행하십시오.
   - 각 단계가 끝날 때마다 명시된 완료 메시지 포맷을 준수하고, 사용자로부터 명시적인 승인(Explicit Approval)을 얻은 후에 다음 단계로 넘어가야 합니다.
   
3. **감사 로그(Audit Log) 기록**:
   - 모든 사용자 입력과 에이전트의 응답은 `aidlc-docs/audit.md`에 타임스탬프(ISO 8601 포맷)와 함께 완벽히 기록되어야 합니다.
   - 사용자 입력을 요약하거나 생략하지 말고, 제공된 그대로 원본을 기록하십시오.
   - `audit.md`를 편집할 때는 기존 내용을 덮어쓰지 말고 반드시 내용을 추가(Append)하십시오.

4. **문서 작성 언어**:
   - AI-DLC 산출물 및 개발 관련 문서는 달리 명시되지 않는 한 **한국어**로 작성하십시오.

5. **문서 작성**:
   - 모든 파일 읽기 및 쓰기는 UTF-8(BOM 없음)으로 수행할 것
