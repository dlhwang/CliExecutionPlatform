# 기능 설계 계획서 (Unit 3: CLI Runner Service - Functional Design Plan)

본 문서는 **Unit 3: CLI Execution Runner**의 상세 기능 설계(Functional Design)를 수행하기 위한 계획서 및 의사결정 질문지입니다. 본 계획안은 설계의 기준점(Single Source of Truth)으로 작동합니다.

---

## 1. 구현 컨텍스트 및 의존성 (Context & Dependencies)

* **대상 개발 유닛**: Unit 3: CLI Execution Runner
* **목적**: Pydantic 액션 플랜 중 `RUN_TOOL` 액션이 들어왔을 때, OpenSCAD CLI 프로세스를 안전하고 제한된 리소스 한도 내에서 가동하는 비즈니스 컴포넌트를 설계합니다.
* **의존성**:
  * Unit 1 (database.py, jobs/models.py, storage/local.py)
  * Unit 2 (llm/schemas.py, llm/parser.py, llm/validator.py)

---

## 2. 의사결정을 위한 공개 질문지 (Open Questions)

> [!IMPORTANT]
> **Unit 3의 기능 설계를 구체화하기 위해 아래 질문에 답변해 주십시오.**  
> 각 질문에 대해 적절한 옵션을 선택하거나 세부 사항을 기재해 주십시오.

### 질문 1. 프로세스 로그 수집 및 실시간 전송 전략
OpenSCAD CLI 구동 시 실시간으로 출력되는 표준 출력(stdout) 및 표준 에러(stderr) 로그를 어떻게 데이터베이스에 기록하고 SSE로 흘려보낼까요?

A) 동기식 버퍼링 후 일괄 기록: CLI 프로세스 실행 도중에는 출력을 메모리에 버퍼링한 후, 실행이 종료되거나 예외가 난 시점에 stdout/stderr 내용을 한데 묶어 단일 EventLog 엔티티로 DB에 INSERT 함. (DB 부하 최소화)

B) 비동기 라인 단위 실시간 기록: CLI 프로세스가 실행되는 동안 한 줄 한 줄 출력되는 내용을 비동기적으로 DB event_logs 테이블에 개별 INSERT 하여 프론트엔드에서 SSE를 통해 즉시 실시간 렌더링되게 함. (실시간 로그 시인성 극대화)

C) Other (please describe after [Answer]: tag below)

[Answer]: B


### 질문 2. CLI 실행 실행 파일(Binary) 경로 관리 방식
서버가 OpenSCAD CLI를 호출할 때 사용할 바이너리 경로를 어떻게 관리하도록 설계할까요?

A) 시스템 PATH 의존: 호스트 OS 시스템의 PATH 환경 변수에 등록된 openscad 기본 명령어를 그대로 호출함. (배포 서버에 openscad가 글로벌하게 깔려 있다고 가정)

B) 환경 변수 파일 구성: .env 환경 변수 파일에 OPENSCAD_BIN_PATH 설정을 추가하여, 각 로컬 및 운영 환경마다 서로 다른 절대 경로의 openscad 실행 파일을 직접 맵핑할 수 있도록 함. (이식성 및 격리 운영 최적화)

C) Other (please describe after [Answer]: tag below)

[Answer]: B


### 질문 3. 실행 예외 발생 시 DB 상태 제어 정책
subprocess 실행 도중 타임아웃(30초) 초과 혹은 프로세스 크래시(Exit Code Non-Zero) 등의 실행 에러 발생 시, Job의 상태 변경 및 에러 로깅은 어떻게 처리할까요?

A) 즉시 실패 마감: 타임아웃 또는 프로세스 비정상 종료 시 즉시 해당 에러 내용을 event_logs 에 기록하고, Job 테이블의 status를 FAILED로 마감함. (즉시 실패 Fail-Fast 보장)

B) 실패 상태 전이 보류: 실행기 내부에서는 에러를 던지기만 하고, 오케스트레이터(Unit 5)나 상위 라우터에서 재시도 여부 또는 최종 실패 처리를 중앙 집중하여 통제하도록 함.

C) Other (please describe after [Answer]: tag below)

[Answer]: B

---

## 3. 기능 설계 세부 수행 계획 (Functional Design Checklist)

본 계획서 승인 이후 순차적으로 수행할 상세 Checklist입니다.

- [x] **Step 1**: Unit 3 비즈니스 논리 모델 설계서 생성 (`business-logic-model.md`)
  - [x] subprocess.Popen / subprocess.run 호출 파라미터 매핑 규칙 (완료)
  - [x] 타임아웃 및 프로세스 강제 종료(Resource cleanup) 알고리즘 (완료)
- [x] **Step 2**: 도메인 엔티티 정의서 생성 (`domain-entities.md`)
  - [x] Runner에서 수집하는 로그 메타데이터 규격 설계 (완료)
- [x] **Step 3**: 비즈니스 규칙 및 검증 규칙서 생성 (`business-rules.md`)
  - [x] 타임아웃(30초) 제한 규칙, 허용 명령어 아규먼트 정합성 규칙 정의 (완료)
- [x] **Step 4**: 최종 기능 설계 결과물 승인 획득 및 NFR Requirements 단계로 전이 (완료: 2026-06-19T10:52:00+09:00)
