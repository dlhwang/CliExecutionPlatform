# 코드 생성 계획서 (Unit 1: API Core & Storage Service - Code Generation Plan)

본 문서는 **Unit 1: API Core & Storage Service**의 애플리케이션 코드 및 테스트 코드를 구현하기 위한 상세 계획서입니다. 본 계획안은 코드 생성의 기준점(Single Source of Truth)으로 작동합니다.

---

## 1. 구현 컨텍스트 및 의존성 (Context & Dependencies)

* **대상 개발 유닛**: Unit 1: API Core & Storage Service
* **적용 범위**: 
  - FastAPI 웹 엔진 및 CORS, REST API 에러 가공 핸들러 구성
  - SQLAlchemy 2.0 ORM 및 PostgreSQL DB Connection Pool 설정
  - `StorageService` 추상 인터페이스 및 Directory Traversal 방어가 탑재된 `LocalStorageService` 구현
  - Job 생성 API (`POST /api/v1/jobs`) 및 아티팩트 다운로드 API (`GET /api/v1/jobs/{job_id}/artifacts/{filename}`) 개발
* **의존성 대상**: Python 3.10+, PostgreSQL 데이터베이스
* **구현 패키지 구조**: 도메인 중심 구조 (`jobs/`, `storage/`, `tests/` 등)

---

## 2. 스토리 추적성 및 검증 계획 (Story Traceability & Testing)

본 유닛은 다음 사용자 스토리를 구현하고 검증합니다.

### 2.1 대상 스토리 매핑
* **Story S-1: 자연어 기반 설계 Job 요청**
  - **인수 기준**: `POST /api/v1/jobs` 호출 시 즉시 UUIDv7 형식의 `job_id` 발급, DB에 `CREATED` 상태로 등록, `.workspaces/jobs/{job_id}/` 및 `.workspaces/artifacts/{job_id}/` 로컬 디렉토리 물리적 생성 완료.
* **Story S-4: Artifact 미리보기 및 다운로드**
  - **인수 기준**: 성공(`COMPLETED`)한 Job의 영구 아티팩트 폴더에 존재 장치가 확인된 바이너리 파일 다운로드 제공. 비인가 경로 탈출(`../`) 요청 시 `403 Forbidden` 반환.

### 2.2 테스트 검증 시나리오 및 파일 스펙
* **테스트 파일 경로**: `tests/test_unit_1.py`
* **주요 테스트 시나리오 (Assertions)**:
  1. **Job 생성 및 Workspace 생성 검증 (`test_job_creation`)**:
     * `POST /api/v1/jobs`에 유효한 prompt(길이 5~1000자) 전송 시 HTTP 201 응답 수신 확인.
     * 반환된 `job_id`가 UUIDv7 규격인지 검증.
     * 데이터베이스에 Job 상태가 `CREATED`로 저장되었는지 조회.
     * 호스트 파일 시스템 상에 `.workspaces/jobs/{job_id}` 및 `.workspaces/artifacts/{job_id}` 디렉토리가 실제로 생성되었는지 `Path.exists()` 확인.
  2. **경로 탈출 공격 방어 검증 (`test_directory_traversal_protection`)**:
     * `GET /api/v1/jobs/{job_id}/artifacts/../../etc/passwd` 와 같은 악성 경로 요청 시, `403 Forbidden` 상태코드 및 에러 코드 `FORBIDDEN_ACCESS` 응답 확인.
     * `LocalStorageService` 단위 테스트에서 허용 영역 밖의 경로 입력을 주입했을 때 `PermissionError` 예외가 정상 트리거되는지 검증.
  3. **API 속도 제한 작동 검증 (`test_rate_limiting`)**:
     * 동일 IP에서 `POST /api/v1/jobs` API를 분당 10회 초과(예: 11회 반복 호출)하여 전송 시, 11번째 요청에서 HTTP 400 (또는 설정된 속도 초과 에러코드) 반환 확인.
  4. **아티팩트 스트리밍 다운로드 검증 (`test_artifact_download`)**:
     * 임의로 생성한 가상 아티팩트 파일을 영구 보관소 폴더에 저장한 후 `GET /api/v1/jobs/{job_id}/artifacts/{filename}` 호출 시 파일 바이트가 원본과 일치하게 다운로드되는지 검증.

---

## 3. 세부 코드 생성 순서 (Numbered Implementation Steps)

모든 작업은 아래의 번호 순서에 따라 차례대로 진행되며, 완료 시마다 체크박스 `[x]`가 업데이트됩니다.

### 1단계: 프로젝트 환경 구성 (Environment Setup)
- [x] **Step 1**: 루트 경로에 `requirements.txt` 생성 (FastAPI, SQLAlchemy, psycopg2-binary, uuid6, slowapi, pytest, httpx 등 탑재)
- [x] **Step 2**: 데이터베이스 연동용 공통 모듈 `database.py` 생성 (`create_engine` 커넥션 풀 매개변수 `pool_size=2`, `max_overflow=3`, `pool_pre_ping=True` 탑재)

### 2단계: 저장소 레이어 구현 (Storage Layer Implementation)
- [x] **Step 3**: `storage/interface.py` 생성 (`StorageService` 추상 베이스 클래스 정의) [S-4 매핑]
- [x] **Step 4**: `storage/local.py` 생성 (`LocalStorageService` 구현 및 `Path.resolve()` 기반의 Directory Traversal 방어 캡슐화 구현) [S-1, S-4 매핑]

### 3단계: 도메인 엔티티 및 스키마 구현 (Domain Entity & Schemas)
- [x] **Step 5**: `jobs/models.py` 생성 (PostgreSQL 매핑용 `Job` 및 `EventLog` SQLAlchemy ORM 모델 정의 - 기본 키 UUIDv7 매핑) [S-1, S-2 매핑]
- [x] **Step 6**: `jobs/schemas.py` 생성 (Pydantic 요청/응답 DTO 정의 및 REST API 표준 에러 스키마 선언) [S-1, S-4 매핑]

### 4단계: 비즈니스 로직 및 API 구현 (Business Logic & API Routers)
- [x] **Step 7**: `jobs/service.py` 생성 (Job 생성, Workspace 초기화, 아티팩트 경로 조회를 관리하는 `JobService` 비즈니스 로직 구현) [S-1, S-4 매핑]
- [x] **Step 8**: `jobs/router.py` 생성 (FastAPI Endpoint 등록: POST 및 GET 라우트 구현) [S-1, S-4 매핑]

### 5단계: 애플리케이션 진입점 및 미들웨어 통합 (Application Entrypoint)
- [x] **Step 9**: `main.py` 생성 (CORS 미들웨어, `slowapi` 속도 제한 등록, lifespan shutdown 복구 로직, 전역 예외 처리 가공기 등록) [S-1, S-4 매핑]

### 6단계: 테스트 코드 작성 및 검증 (Testing & Verification)
- [x] **Step 10**: `tests/conftest.py` 생성 (SQLite 인메모리 혹은 테스트용 PostgreSQL 데이터베이스를 연동하는 pytest 세션 피처 구성)
- [x] **Step 11**: `tests/test_unit_1.py` 생성 (인수 기준 검증용 통합 테스트 시나리오 4종 구현 및 검증 실행)

---

## 4. 완료 조건 (Completion Criteria)
1. `requirements.txt`에 명시된 의존 패키지가 정상 설치되고 로컬 uvicorn 가동에 이상이 없음.
2. `tests/test_unit_1.py` 내의 모든 테스트(Job 생성, Directory Traversal 차단, 속도 제한, 아티팩트 다운로드)가 패스하고, 이에 매핑된 S-1, S-4 스토리의 인수 조건이 충족됨.
3. 생성된 코드가 `aidlc-docs/` 외곽의 올바른 애플리케이션 물리 경로에 작성됨.
