# 비기능 상세 설계 계획서 (Unit 2: Parser & Policy Validator Service - NFR Design Plan)

본 문서는 **Unit 2: Parser & Policy Validator Service**의 비기능 상세 설계(NFR Design)를 수행하기 위한 계획서 및 질문지입니다.

---

## 1. 개요 및 목적 (Goal Description)

* **대상 개발 유닛**: Unit 2: LLM Plan Parser & Validator
* **목적**: NFR Requirements에서 정한 품질 목표(500ms 레이턴시, `SECURITY_ALERT` DB 감사 적재, `LLMPlanRetryableException` 재시도 예외 구조)를 실현하기 위한 디자인 패턴 및 논리적 컴포넌트를 설계합니다.

---

## 2. 의사결정을 위한 공개 질문지 (Open Questions)

> [!IMPORTANT]
> **Unit 2의 비기능 상세 설계를 위해 아래 질문에 답변해 주십시오.**  
> 각 질문에 대해 적절한 옵션을 선택하거나 세부 사항을 기재해 주십시오.

### 질문 1. 성능 패턴: 파일시스템 경로 검사 지연 방지 전략
로컬 파일/디렉토리 검사 시 발생하는 디스크 I/O 지연을 500ms 이내로 방어하기 위한 경로 검증 성능 최적화 패턴은 무엇입니까?
* **옵션 A (동기식 직접 조회)**: 파일 입출력 시 발생하는 오버헤드가 크지 않으므로, 캐싱 없이 매번 `pathlib`을 이용해 정밀하고 직관적으로 실시간 디스크 조회를 수행. (안정성 극대화)
* **옵션 B (경로 상태 캐싱 기법)**: 동일 Job 라이프사이클 내에서 중복 조회되는 경로에 대해 인메모리 캐시를 적용해 디스크 쿼리를 최소화함.
* **선택**: 
[Answer]: A

### 질문 2. 보안 패턴: 침투 시도 감지 시 감사 로그 DB 적재 방식
보안 정책 위반 발생 시 `SECURITY_ALERT` 타입의 이벤트 로그를 데이터베이스에 적재하는 방식을 어떻게 구성할까요?
* **옵션 A (동기식 즉시 적재)**: 감사 정보 유실을 원천 차단하기 위해, API 예외 응답을 반환하기 전에 동기적으로 DB INSERT를 완료함. (감사 무결성 보장)
* **옵션 B (비동기 위임 적재)**: 응답 속도 지연을 방지하기 위해, FastAPI `BackgroundTasks` 혹은 비동기 태스크를 이용해 백그라운드에서 DB INSERT 처리.
* **선택**: 
[Answer]: A

### 질문 3. 회복성 패턴: 재시도 예외 클래스의 상세 에러 컨텍스트 설계
LLM JSON 파싱 오류 시 던져지는 `LLMPlanRetryableException` 내부에 어떤 상세 에러 정보를 담아 오케스트레이터로 전달할까요?
* **옵션 A (상세 피드백 컨텍스트 탑재)**: 발생한 파싱 에러 메시지(예: JSONDecodeError 원인)뿐만 아니라, 문제가 발생한 원본 텍스트 및 파싱 도중 에러가 난 위치 등의 상세 컨텍스트를 구조화해 담아서 LLM에게 정확한 자가 치유(Self-Healing) 프롬프트를 쏠 수 있도록 함.
* **옵션 B (단순 메시지 탑재)**: 예외 발생 원인 메시지만 단순 텍스트로 담아 간결하게 전달.
* **선택**: 
[Answer]: A

---

## 3. 비기능 상세 설계 세부 수행 계획 (NFR Design Checklist)

본 계획서 승인 이후 순차적으로 수행할 상세 Checklist입니다.

- [x] **Step 1**: Unit 2 비기능 디자인 패턴 설계서 생성 (`nfr-design-patterns.md`)
  - 예외 계층 아키텍처 다이어그램 및 설계 명세
  - 보안 및 성능 패턴(동기식 Audit Trail) 구체화
- [x] **Step 2**: 논리 아키텍처 컴포넌트 명세 생성 (`logical-components.md`)
  - `ActionPlanParser`, `SecurityPolicyValidator`, `LLMPlanRetryableException` 컴포넌트 관계 및 DSN/에러 매핑 흐름도 작성 (Mermaid 활용)
