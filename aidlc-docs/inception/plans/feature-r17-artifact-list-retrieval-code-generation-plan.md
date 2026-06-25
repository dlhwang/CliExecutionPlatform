# Code Generation Plan - FEATURE R-17 (Job ID 기반 아티팩트 목록 조회 API)

본 계획서는 **FEATURE R-17 (Job ID 기반 아티팩트 목록 조회 API)**을 구현하기 위한 코드 생성 계획입니다. 이 계획서는 본 단계의 단일 진실 공급원(Single Source of Truth)으로 사용되며, 모든 구현과 테스트 작성은 본 순서에 맞춰 진행됩니다.

## 1. Unit Context & Details

- **대상 컴포넌트**: `jobs` (router.py, service.py, schemas.py) 및 `tests` (test_unit_2.py)
- **구현 대상 Story**: 단순 API 엔드포인트 요건으로 별도의 사용자 스토리는 Skip되었으나, 아래의 Requirement R-17을 완전히 검증해야 함.
- **의존성 모듈**: `database.py` (DB 세션 연결)
- **비즈니스 예외 규정**:
  - 존재하지 않는 `job_id` 조회 시 HTTP 404 Not Found 반환 (에러 코드: `NOT_FOUND`)
  - 존재하는 Job이나 상태가 `COMPLETED`가 아닌 경우 (예: CREATED, RUNNING, FAILED) HTTP 400 Bad Request 반환 (에러 코드: `BAD_REQUEST`)
- **보안 검증 및 제한**:
  - 응답 구조에 `relative_path`나 호스트 내 물리적 디렉토리 구조가 일절 노출되지 않도록 전용 Pydantic Response 스키마를 사용하여 출력 필터링.

---

## 2. Requirement Traceability Plan (요구사항 추적 및 검증 계획)

| Requirement/Story | Acceptance Criteria | Required Test Evidence | Test Level | Planned Test File / Scenario | Required Result |
| --- | --- | --- | --- | --- | --- |
| R-17 | `COMPLETED` 상태의 Job에 매핑된 아티팩트 목록이 정상 반환되는가 | `id`, `filename`, `content_type`, `created_at` 필드가 반환되는지 assertion 검증 | unit/integration | `tests/test_unit_2.py` | Pass |
| R-17 | DB에 존재하지 않는 `job_id` 조회 시 404 Not Found를 발생하는가 | HTTP status 404 및 에러 코드 `NOT_FOUND` 검증 | unit/integration | `tests/test_unit_2.py` | Pass |
| R-17 | Job 상태가 `COMPLETED`가 아닐 때 (CREATED, RUNNING, FAILED) 400 Bad Request를 발생하는가 | HTTP status 400 및 에러 코드 `BAD_REQUEST` 검증 | unit/integration | `tests/test_unit_2.py` | Pass |
| R-17 | 반환 스키마에 `relative_path` 정보가 차단되었는가 | 응답 JSON에 `relative_path` 키가 존재하지 않는지 assertion 검증 | unit/integration | `tests/test_unit_2.py` | Pass |
| 회귀 방지 | 기존의 모든 92개 테스트 스위트가 통과하는가 | 기존 테스트 성공 검증 | integration | 전체 pytest 명령어 실행 | Pass |

---

## 3. Detailed Code Generation Steps (체크리스트)

### [x] Step 1: `jobs/schemas.py` 에 아티팩트 목록 응답 스키마 추가
- **대상 파일**: `jobs/schemas.py`
- **변경 사항**: 아티팩트 목록 응답 전용 Pydantic 모델 `ArtifactListResponse` 추가
  - 포함할 필드: `id: UUID`, `filename: str`, `content_type: str`, `created_at: datetime`
  - SQLAlchemy 호환 설정: `model_config = ConfigDict(from_attributes=True)` 설정 적용

### [x] Step 2: `jobs/service.py` 에 아티팩트 목록 조회 메서드 추가
- **대상 파일**: `jobs/service.py`
- **변경 사항**: `ArtifactService` 클래스 내에 `get_artifacts_by_job_id(self, job_id: UUID) -> List[Artifact]` 메서드 작성
  - 해당 `job_id`를 FK로 가진 모든 `Artifact` 레코드를 DB에서 조회해 리스트로 반환하는 로직 구현

### [x] Step 3: `jobs/router.py` 에 아티팩트 목록 조회 API 구현
- **대상 파일**: `jobs/router.py`
- **변경 사항**: 아티팩트 목록 조회 라우터 엔드포인트 구현
  - `GET /api/v1/jobs/{job_id}/artifacts` 경로 및 `response_model=List[ArtifactListResponse]` 스펙 적용
  - 핵심 비즈니스 로직 분기 구현:
    1. `job_service.get_job(job_id)` 호출하여 Job 존재 여부 파악. 미존재 시 `HTTP_404_NOT_FOUND` 에러 반환.
    2. `job.status != "COMPLETED"` 조건 검사. 완료 상태가 아닐 시 `HTTP_400_BAD_REQUEST` 에러 반환.
    3. `artifact_service.get_artifacts_by_job_id(job_id)` 호출하여 아티팩트 목록 조회 후 응답 반환.

### [x] Step 4: `tests/test_unit_2.py` 에 신규 엔드포인트에 대한 자동화 테스트 코드 추가
- **대상 파일**: `tests/test_unit_2.py`
- **변경 사항**:
  - `test_get_artifacts_success`: `COMPLETED` 상태의 Job과 매핑된 아티팩트가 있을 때, 200 OK 및 올바른 아티팩트 목록(`relative_path` 미포함)이 반환되는지 확인.
  - `test_get_artifacts_not_found`: 존재하지 않는 `job_id` 조회 시 404 에러와 `NOT_FOUND` 에러 코드가 발생하는지 확인.
  - `test_get_artifacts_not_completed`: Job은 존재하나 상태가 `RUNNING`, `FAILED`, `CREATED` 등 `COMPLETED`가 아닐 때 400 에러와 `BAD_REQUEST` 에러 코드가 발생하는지 확인.

### [x] Step 5: `pytest` 실행을 통한 통합 검증 및 회귀 테스트 수행
- **실행 명령**: `pytest`
- **검증 사양**: 기존 92개 테스트와 신규 작성한 3개 이상의 테스트를 합쳐 총 95개 이상의 테스트 스위트가 모두 회귀 없이 정상 통과하는지 검증.

### [x] Step 6: 구현 결과 요약 문서 작성
- **대상 파일**: `aidlc-docs/construction/feature-r17-artifact-list-retrieval/code/feature-r17-artifact-list-retrieval-summary.md` [NEW]
- **변경 사항**: 변경/추가된 소스 파일 목록, 테스트 실행 로그 및 요구사항 추적성 매핑 상태를 기록한 요약 마크다운 문서 작성.
