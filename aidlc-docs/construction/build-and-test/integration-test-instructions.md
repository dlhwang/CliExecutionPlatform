# 통합 테스트 지침 (Integration Test Instructions)

본 지침은 CLI-Execution-Platform 프로젝트의 서비스 간 통합 테스트 및 종단 간(E2E) 시나리오 검증 방법을 설명합니다. 특히 R-16 아티팩트 다운로드 API와 기존 작업 실행/등록 오케스트레이터 간의 연계 동작을 검증합니다.

## 목적
비동기 작업 실행(`orchestrator`), 아티팩트 물리 저장소(`storage`), DB 메타데이터(`Artifact` 모델), API 라우터(`router_artifacts`)의 유기적 흐름이 깨지지 않고 안전하게 연동되는지 검증합니다.

## 통합 테스트 시나리오

### 시나리오 1: LLM Action Execution → Artifact 등록 연계 (등록 시나리오)
- **설명**: LLM 작업(Action Plan) 처리 중 `CREATE_ARTIFACT` 액션 발생 시, 물리 파일이 작업 샌드박스(`/jobs/{job_id}`) 내에 생성되고, DB 트랜잭션 내에서 `ArtifactService`를 통해 안전하게 등록되는지 검증합니다.
- **주요 검증 조건**:
  - `ActionExecutor.save_artifact` 수행 후 DB 메타데이터 트랜잭션 등록 여부.
  - 트랜잭션 롤백 시 생성된 물리 파일이 삭제(best-effort cleanup)되는지 여부.
- **실행 명령**:
  ```bash
  # Windows PowerShell
  $env:PYTHONPATH="."
  venv\Scripts\pytest tests/test_unit_5.py -k "test_orchestrator"
  ```

### 시나리오 2: API 클라이언트 아티팩트 다운로드 (다운로드 시나리오)
- **설명**: 외부 클라이언트가 HTTP GET 요청(`GET /api/v1/artifacts/{artifact_id}/download`)을 통해 아티팩트를 요청할 때, Uvicorn 개발 서버와 API 라우터가 `FileResponse` 형태로 파일을 정상 반환하는지 검증합니다.
- **주요 검증 조건**:
  - 존재하지 않는 ID 시 HTTP 404 응답 확인.
  - 허용되지 않는 경로(/etc/passwd, ../ 탈출 등) 조회 시 HTTP 403 응답 확인.
  - 성공 시 HTTP 200 응답 및 `Content-Type`, `Content-Disposition` (filename 검증 가능 포맷) 헤더 확인.
- **실행 명령**:
  ```bash
  # Windows PowerShell
  $env:PYTHONPATH="."
  venv\Scripts\pytest tests/test_unit_2.py -k "test_artifact_download"
  ```

## 통합 테스트 환경 실행 단계

### 1. 로컬 테스트 서버(Uvicorn) 실행
```bash
# Windows PowerShell
$env:PYTHONPATH="."
venv\Scripts\python main.py
```
- **기대 결과**: Uvicorn 서버가 `http://127.0.0.1:8000`에서 가동됩니다.

### 2. 수동 통합 API 호출 예시 (Powershell)
테스트 스크립트 외에 cURL이나 Powershell `Invoke-RestMethod`를 사용하여 다운로드 엔드포인트를 수동 테스트할 수 있습니다.
```powershell
# 임의의 등록되지 않은 Artifact ID로 호출 시 404 응답 검증
try {
    Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/v1/artifacts/00000000-0000-0000-0000-000000000000/download"
} catch {
    Write-Host "Response Status Code: $($_.Exception.Response.StatusCode)" # 404 Expected
}
```

### 3. 테스트 후 정리
동작 확인이 끝난 테스트 환경은 Uvicorn 프로세스를 종료(`Ctrl+C`)하고 임시 파일 공간을 리셋합니다.
