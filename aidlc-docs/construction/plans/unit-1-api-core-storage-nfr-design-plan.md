# 비기능 설계 계획서 (Unit 1: API Core & Storage Service - NFR Design Plan)

본 문서는 **Unit 1: API Core & Storage Service**의 비기능 요건들을 시스템 아키텍처 및 디자인 패턴으로 녹여내기 위한 설계 계획 및 핵심 질의서입니다.

---

## 1. 실행 체크리스트 (Execution Checklist)

이 계획에 따라 Unit 1의 비기능 설계 패턴을 결정하고 세부 논리 컴포넌트 구조를 설계합니다.

### 기획 및 질의 단계 (Planning & Questions)
- [x] **Step 1**: Unit 1 비기능 요구사항(NFR Requirements) 분석 완료
- [x] **Step 2**: 비기능 설계 계획서 작성 및 질문 임베드 (`unit-1-api-core-storage-nfr-requirements-plan.md` 작성 완료)
- [x] **Step 3**: 사용자 답변 수집 및 모호성 분석 (완료)
- [x] **Step 4**: 비기능 설계 계획안에 대한 명시적 승인 획득 (완료)

### 상세 설계 단계 (Detailed Design Phase)
- [x] **Step 5**: 비기능 디자인 패턴 설계서 생성 (`nfr-design-patterns.md`)
  * 재해 복구, 속도 제한 필터링, 경로 보안 격리 패턴 정의
- [x] **Step 6**: 논리 아키텍처 컴포넌트 명세 생성 (`logical-components.md`)
  * 스토리지 레이어, 예외 가공기, 속도 제한기 연동 구조 설계
- [x] **Step 7**: 비기능 설계 최종 산출물에 대한 명시적 승인 획득 (완료)

---

## 2. 비기능 설계 단계 질의사항 (NFR Design Questions)

비기능 디자인 패턴 구체화를 위해 아래 질문들에 답변해 주시기 바랍니다.

### 질문 2.1: 데이터베이스 장애 복구 및 재시도(Retry) 패턴
서버 가동 중 데이터베이스 서버의 일시적인 네트워크 순단이나 장애 발생 시, API 레벨에서 어떤 복구(Resilience) 패턴을 적용하시겠습니까?
- **A) SQLAlchemy Pre-ping 패턴 단독 사용 (Fail-Fast)**: 커넥션을 풀에서 꺼낼 때 생존 검사(`pool_pre_ping=True`)를 통해 끊긴 연결을 즉시 버리고 재연결함. 네트워크 단기 순단은 풀 레이어에서 커버하고, 실제 DB 하드 장애는 즉시 에러 반환. (추천)
- **B) API 비즈니스 로직 단위의 재시도(Retry) 패턴 적용**: DB 조회 예외 발생 시, 데코레이터(예: `tenacity` 라이브러리)를 이용해 0.5초 간격으로 최대 3회 재시도를 가동한 후 예외 처리.
- **X) 기타**

[Answer]: A

---

### 질문 2.2: 경로 탈출(Directory Traversal) 보안 검증 패턴의 위치
임시 디렉토리 상위 경로를 조작하여 시스템 파일을 침투하는 것을 막기 위한 검증(Security Validation) 로직을 아키텍처의 어느 레이어에 배치하시겠습니까?
- **A) StorageService 구현 클래스 내부 100% 캡슐화**: 파일의 생성/읽기/쓰기 등이 물리 파일 시스템에 닿기 직전 단계인 `LocalStorageService` 내부 메서드 초입에서 무조건 경로 검증 함수를 실행하도록 강제함. (결함 발생을 막는 가장 강력한 캡슐화 방법) - (추천)
- **B) API Router 및 Storage 레이어 이중 검증**: FastAPI의 Router 진입 단계에서 1차 검증(인수 유효성 차원)을 수행하고, `LocalStorageService` 내부에서 2차 검증을 병행함.
- **X) 기타**

[Answer]: A

---

### 질문 2.3: 애플리케이션 강제 종료 시의 비동기 Job 상태 정합성 복구 패턴
FastAPI 서버가 재부팅되거나 강제 종료(SIGTERM 등)될 때, 백그라운드 태스크에서 실행 중이던 비동기 Job들의 데이터베이스 상태 정합성(Status Consistency)을 어떻게 복구하시겠습니까?
- **A) 애플리케이션 시작(Startup) 시 미완결 Job 상태 스캔 및 일괄 복구**: FastAPI 앱이 새로 구동되는 시점(lifespan startup)에 DB를 조회하여 `CREATED` 혹은 `RUNNING` 상태로 멈춰 있는 모든 Job을 `FAILED` 상태로 업데이트하고 로그에 기록함. (추천)
- **B) ASGI Shutdown 시그널을 통한 우아한 종료(Graceful Shutdown)**: FastAPI의 shutdown lifespan 핸들러에서 현재 처리 중인 Job 리스트를 추적하여 데이터베이스에 FAILED 상태를 기록하고 자원을 비우는 시그널 핸들링 장치 추가. (비정상 강제 종료 시에는 작동하지 않을 수 있음)
- **X) 기타**

[Answer]: B
