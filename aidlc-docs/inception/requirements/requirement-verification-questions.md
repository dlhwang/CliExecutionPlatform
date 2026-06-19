# 요구사항 검증 질문 (Requirement Verification Questions) - 답변 완료

프로젝트: **LLM 기반 Workspace CLI Execution Platform**

아래 질문들에 대해 사용자가 답변한 내용입니다.

---

## 1. 기술 스택 및 아키텍처 관련 질문

### 질문 1.1: Backend API 기술 스택
본 플랫폼의 Backend API로 제안된 후보군 중 어떤 기술 스택을 선호하십니까?
- **A) Spring Boot (Java)**: 엔터프라이즈 환경에서의 안정성 및 풍부한 에코시스템 활용
- **B) FastAPI (Python)**: LLM 연동성 및 CLI 실행기(Worker) 개발의 용이성
- **X) 기타** (아래 [Answer]: 뒤에 구체적으로 적어주세요)

[Answer]: B) FastAPI (Python) - LLM 연동성 및 CLI 실행기(Worker) 개발 용이

---

### 질문 1.2: CLI 실행 격리 수준 (Docker Sandbox)
첫 번째 대상 도구인 OpenSCAD CLI를 실행할 때, MVP 단계에서 격리 환경을 어떻게 구성할 것입니까?
- **A) Docker Sandbox 즉시 도입**: 처음부터 Docker 컨테이너 내에서 OpenSCAD CLI를 실행하도록 구현 (보안성 높음)
- **B) 로컬 프로세스 격리 우선 도입**: MVP에서는 서버 로컬 프로세스로 실행하되, OS 수준의 timeout, CPU/메모리 제한 및 디렉토리 접근 차단(상대경로 검증)을 적용하고 Docker 도입은 다음 단계로 연기
- **X) 기타** (아래 [Answer]: 뒤에 구체적으로 적어주세요)

[Answer]: B) 로컬 프로세스 격리 우선 도입 (MVP에서는 OS 수준의 timeout, CPU/메모리 제한, 디렉토리 접근 차단 적용 후 차후 Docker 확장)

---

### 질문 1.3: 이벤트 저장 및 Queue 메커니즘
SSE를 통한 실시간 진행 상황 전송 및 Last-Event-ID 기반 누락 복구를 위해, 이벤트 및 Queue 메커어니즘을 MVP에서 어떻게 구성할 것입니까?
- **A) 데이터베이스(PostgreSQL) 폴링 및 저장**: 이벤트를 DB 테이블에 기록하고 Last-Event-ID 요청 시 DB에서 조회하여 복구
- **B) Redis Pub/Sub 및 DB 저장**: 실시간 전달은 Redis Pub/Sub을 활용하고, 백업 및 복구를 위해 DB 또는 Redis에 이벤트 로그를 저장
- **C) Redis Streams 도입**: 메시지 큐와 이벤트 스트림(Last-Event-ID 복구용) 역할을 Redis Streams로 단일화하여 처리
- **X) 기타** (아래 [Answer]: 뒤에 구체적으로 적어주세요)

[Answer]: A) 데이터베이스(PostgreSQL) 폴링 및 저장 (이벤트를 DB 테이블에 기록하고 Last-Event-ID 요청 시 DB에서 조회하여 복구)

---

### 질문 1.4: Artifact 저장소 구성
생성된 model.scad, preview.png, output.stl 등의 Artifact를 저장할 환경을 MVP에서 어떻게 구성할 것입니까?
- **A) 로컬 파일 시스템 (Local Filesystem)**: 서버 로컬 디렉토리에 Job ID별로 저장하되, 추후 S3 전환이 가능하도록 Storage 인터페이스로 추상화
- **B) AWS S3 호환 Object Storage**: 처음부터 S3나 LocalStack/MinIO를 연동하여 저장
- **X) 기타** (아래 [Answer]: 뒤에 구체적으로 적어주세요)

[Answer]: A) 로컬 파일 시스템 (서버 로컬 디렉토리에 Job ID별로 저장하되, 추후 S3 전환이 가능하도록 Storage 인터페이스로 추상화)

---

### 질문 1.5: LLM Action Plan 구성 및 Validation
LLM이 생성하는 제한된 JSON action plan의 파싱 및 검증 규칙에 대해, MVP에서 차단해야 할 절대 경로 및 상위 경로(`../`) 검증 외에 추가로 필요한 보안 제약 사항이 있습니까?
(예: 특정 파일 확장자 제한, 허용된 툴의 arguments 화이트리스트 등)

[Answer]: 특별한 추가 제약은 없으며, 기본적으로 상위 디렉토리 탈출 검증(`../` 차단 및 absolute path 차단) 및 허용된 작업(CREATE_DIRECTORY, WRITE_FILE, RUN_TOOL, CREATE_ARTIFACT) 검증에 초점을 맞춥니다.

---

## 2. 확장 기능 적용 여부 질문 (Extension Opt-In)

### 질문 2.1: 보안 기본 확장 기능 (Security Baseline Extension)
본 프로젝트에 보안 기본 확장 규칙을 적용할 것입니까?
- **A) Yes**: 모든 SECURITY 규칙을 블로킹 제약 조건으로 적용합니다. (프로덕션 수준의 애플리케이션에 권장)
- **B) No**: 모든 SECURITY 규칙을 건너뜁니다. (PoC, 프로토타입, 실험적 프로젝트에 적합)
- **X) 기타** (아래 [Answer]: 뒤에 구체적으로 적어주세요)

[Answer]: B) No — 모든 SECURITY 규칙 건너뛰기 (PoC, 프로토타입, 실험적 프로젝트에 적합)

---

### 질문 2.2: 속성 기반 테스트 확장 기능 (Property-Based Testing Extension)
본 프로젝트에 속성 기반 테스트(PBT) 규칙을 적용할 것입니까?
- **A) Yes**: 모든 PBT 규칙을 블로킹 제약 조건으로 적용합니다. (비즈니스 로직, 데이터 변환, 직렬화 또는 상태 저장 컴포넌트가 있는 프로젝트에 권장)
- **B) Partial**: 순수 함수(Pure function) 및 직렬화 라운드트립에 대해서만 PBT 규칙을 적용합니다. (알고리즘 복잡도가 제한적인 프로젝트에 적합)
- **C) No**: 모든 PBT 규칙을 건너뜁니다. (단순 CRUD 애플리케이션, UI 전용 프로젝트, 또는 중요한 비즈니스 로직이 없는 얇은 통합 레이어에 적합)
- **X) 기타** (아래 [Answer]: 뒤에 구체적으로 적어주세요)

[Answer]: C) No — 모든 PBT 규칙 건너뛰기 (단순 CRUD 애플리케이션, UI 전용 프로젝트, 또는 중요한 비즈니스 로직이 없는 얇은 통합 레이어에 적합)
