# 비즈니스 규칙 및 검증 규칙서 (Business Rules & Validation) - Unit 1: API Core & Storage Service

본 문서는 **Unit 1: API Core & Storage Service**의 저장소 물리 디렉토리 설계 규칙, `StorageService`인터페이스의 요구 기능 스펙, 그리고 API 레벨에서의 유효성 검증 및 에러 처리 정책을 명세합니다.

---

## 1. 물리 작업 공간 및 파일 처리 규칙 (Workspace & File Rules)

모든 작업 공간 관리 및 파일 연산은 아래 명시된 규칙을 엄격히 준수하여 수행되어야 합니다.

### 1.1 물리 디렉토리 구조 규칙
모든 파일 및 아티팩트 처리는 프로젝트 루트 폴더 아래의 `.workspaces` 폴더 내로 격리합니다.
* **프로젝트 루트**: `D:/workspace/CLI-Execution-Platform/`
* **임시 작업 디렉토리 (Temporary Workspace)**: `.workspaces/jobs/{job_id}/`
  * LLM이 코드를 작성하고 OpenSCAD CLI가 중간 코드를 파싱하고 빌드하는 작업 공간입니다.
  * 빌드가 종료되면(성공/실패 여부 상관없이) 디바이스 디스크 정리 정책에 따라 자동 삭제 대상이 됩니다.
* **영구 아티팩트 보관소 (Permanent Artifact Repository)**: `.workspaces/artifacts/{job_id}/`
  * 작업이 성공적으로 종료되어 클라이언트에게 서빙 가능한 최종 산출물(`.stl`, `.png` 등)을 보관하는 장소입니다.
  * 사용자가 파일 다운로드 API를 통해 파일명을 명시하여 다운로드할 수 있는 물리적인 위치입니다.

### 1.2 경로 검증 규칙
* **상대 경로 검증**: LLM이나 API에서 전달되는 모든 파일 경로는 반드시 **상대 경로**여야 합니다.
* **경로 탈출(Directory Traversal) 차단**:
  * 경로에 `../` 또는 `..\\` 문자열이 포함되어 상위 폴더나 호스트 시스템의 중요 경로로 침투하는 동작은 예외 없이 차단됩니다.
  * Python의 `pathlib.Path.resolve()` 메서드를 사용해 최종 물리 경로를 확인한 후, 이 경로가 해당 Job의 물리 디렉토리 하위에 속해 있는지 검증(`is_relative_to()`)합니다.
  * 위반 시 즉시 즉각적인 작업 취소 및 `SecurityException`을 발생시킵니다.

---

## 2. Storage Service 인터페이스 요구사항 (Storage Service Interfaces)

`storage` 도메인 내의 파일 작업 추상 레이어를 마련하기 위한 핵심 인터페이스 명세입니다.

```python
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List
from uuid import UUID

class StorageService(ABC):
    
    @abstractmethod
    def create_workspace(self, job_id: UUID) -> None:
        """
        Job을 위한 임시 작업 디렉토리 및 영구 아티팩트 디렉토리를 로컬에 생성합니다.
        - 임시: .workspaces/jobs/{job_id}/
        - 영구: .workspaces/artifacts/{job_id}/
        """
        pass

    @abstractmethod
    def clean_workspace(self, job_id: UUID) -> None:
        """
        Job의 실행이 종료된 후, 임시 작업 공간(.workspaces/jobs/{job_id}/) 전체를 재귀적으로 삭제합니다.
        (리소스 회수 목적)
        """
        pass

    @abstractmethod
    def write_file(self, job_id: UUID, relative_path: str, content: str | bytes) -> None:
        """
        임시 작업 공간 내부의 지정된 상대경로에 파일을 기록합니다.
        - Directory Traversal 방지 검증을 반드시 거쳐야 합니다.
        """
        pass

    @abstractmethod
    def read_file(self, job_id: UUID, relative_path: str) -> bytes:
        """
        임시 작업 공간 내의 파일 내용을 바이너리로 읽어옵니다.
        - Directory Traversal 방지 검증이 동반됩니다.
        """
        pass

    @abstractmethod
    def save_artifact(self, job_id: UUID, relative_path: str) -> None:
        """
        임시 작업 공간(.workspaces/jobs/{job_id}/{relative_path})에 생성된 산출물을
        영구 아티팩트 보관소(.workspaces/artifacts/{job_id}/{relative_path})로 복사합니다.
        """
        pass

    @abstractmethod
    def check_artifact_exists(self, job_id: UUID, filename: str) -> bool:
        """
        영구 아티팩트 보관소 내에 특정 파일이 존재하는지 검증합니다.
        """
        pass

    @abstractmethod
    def get_artifact_path(self, job_id: UUID, filename: str) -> Path:
        """
        영구 아티팩트 보관소 내 파일의 물리적 경로를 반환합니다. (FileResponse 전송용)
        - 상위 경로 침투 검증 필수
        """
        pass
```

---

## 3. 에러 핸들링 및 검증 정책 (Error Handling & Validation Policies)

### 3.1 HTTP 응답 코드 및 에러 매핑 규칙
시스템에서 예외가 발생할 경우 사전에 정의된 표준 API REST Error Schema에 부합하는 형태로 가공하여 응답합니다.

* **Job 미존재 (HTTP 404 Not Found)**:
  * 에러 메시지: `Job {job_id} not found.`
  * 코드: `NOT_FOUND`
* **아티팩트 파일 미존재 (HTTP 404 Not Found)**:
  * 에러 메시지: `Artifact {filename} not found for Job {job_id}.`
  * 코드: `NOT_FOUND`
* **입력 매개변수 유효성 검증 실패 (HTTP 400 Bad Request)**:
  * 사용자 프롬프트 길이가 5자 미만이거나 1000자를 초과한 경우
  * 에러 메시지: Pydantic이 제공하는 필드 유효성 에러 기반 메시지
  * 코드: `VALIDATION_ERROR`
* **보안 및 경로 Traversal 탐지 시 (HTTP 403 Forbidden)**:
  * 에러 메시지: `Access denied. Path traversal detected.`
  * 코드: `FORBIDDEN_ACCESS`

### 3.2 FastAPI 커스텀 Exception Handler 정책
FastAPI가 기본적으로 던지는 `RequestValidationError` 및 애플리케이션 정의 예외를 가공하기 위해 다음과 같은 전역 익셉션 핸들러를 등록합니다.

```python
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    # Pydantic 필드 검증 에러를 당사 표준 스키마 형태로 변환
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    msg = f"Field '{'.'.join(str(loc) for loc in first_error.get('loc', []))}' : {first_error.get('msg', 'invalid value')}"
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": msg
            }
        }
    )
```
