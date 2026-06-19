# 컴포넌트 메서드 정의서 (Component Methods)

본 문서는 플랫폼 각 핵심 컴포넌트의 메서드 시그니처, 목적, 그리고 입력/출력 데이터 타입을 명세합니다. 세부적인 비즈니스 규칙은 구현(CONSTRUCTION) 단계의 Functional Design에서 확정됩니다.

---

## 1. `jobs` 도메인 컴포넌트 메서드

### JobManager (Job Service & DB Repository)

```python
class JobManager:
    async def create_job(self, prompt: str) -> JobSchema:
        """
        새로운 설계 요청에 대한 Job 레코드를 데이터베이스에 생성합니다.
        - Input: prompt (str) - 사용자의 자연어 요구사항
        - Output: JobSchema - 발급된 Job ID 및 초기 CREATED 상태를 가진 Pydantic 모델
        """
        pass

    async def update_job_status(self, job_id: UUID, status: JobStatus, error_message: str = None) -> JobSchema:
        """
        지정된 Job의 상태를 갱신합니다. 에러 발생 시 에러 메시지를 기록합니다.
        - Input: 
          - job_id (UUID)
          - status (JobStatus) - RUNNING, COMPLETED, FAILED 등
          - error_message (str, optional) - 오류 사유
        - Output: JobSchema - 갱신 완료된 모델
        """
        pass

    async def get_job(self, job_id: UUID) -> JobSchema:
        """
        지정된 Job의 현재 메타데이터 및 상태를 데이터베이스에서 가져옵니다.
        - Input: job_id (UUID)
        - Output: JobSchema
        """
        pass
```

---

## 2. `llm` 도메인 컴포넌트 메서드

### ActionPlanParser

```python
class ActionPlanParser:
    def parse_plan(self, llm_raw_response: str) -> List[ActionSchema]:
        """
        LLM의 마크다운 또는 텍스트 응답에서 JSON Action Plan을 추출 및 구문 분석합니다.
        - Input: llm_raw_response (str)
        - Output: List[ActionSchema] - 검증 가능한 Pydantic 액션 오브젝트 리스트
        - Throws: JSONDecodeError, ValidationError
        """
        pass
```

### SecurityPolicyValidator

```python
class SecurityPolicyValidator:
    def validate_plan(self, workspace_root: Path, plan: List[ActionSchema]) -> None:
        """
        Action Plan 내 모든 액션이 보안 기준을 완벽히 충족하는지 종합적으로 검사합니다.
        - Input:
          - workspace_root (Path) - 해당 Job의 실제 절대 경로
          - plan (List[ActionSchema]) - 파싱된 계획
        - Output: None (검증 통과 시 정상 종료)
        - Throws: SecurityValidationError (경로 Traversal 감지 시, 허용되지 않은 CLI 명령어 수신 시)
        """
        pass

    def check_safe_path(self, workspace_root: Path, relative_path: str) -> Path:
        """
        상대 경로를 해석하여 해당 경로가 물리적으로 workspace_root의 내부에 위치하는지 엄격히 검증합니다.
        - Input:
          - workspace_root (Path)
          - relative_path (str) - LLM이 제안한 상대 경로 (예: "model.scad")
        - Output: Path - 시스템 하위에서 사용 가능한 안전하게 검증된 절대 경로
        - Throws: TraversalAttackException (../ 사용 혹은 절대 경로 지정으로 상위 폴더 진입 시)
        """
        pass
```

---

## 3. `runner` 도메인 컴포넌트 메서드

### CLIExecutionRunner

```python
class CLIExecutionRunner:
    def run_tool(self, workspace_path: Path, tool_name: str, args: List[str], timeout: int = 30) -> CLIResult:
        """
        물리적인 격리 조치를 적용하여 지정된 CLI 도구를 백그라운드로 실행합니다.
        - Input:
          - workspace_path (Path) - Job Workspace 절대 경로
          - tool_name (str) - 실행할 도구 이름 (MVP는 "openscad")
          - args (List[str]) - 인자 리스트
          - timeout (int) - 프로세스 강제 종료 대기 시간 (기본 30초)
        - Output: CLIResult - exit_code, stdout, stderr를 포함한 결과 구조체
        - Throws: TimeoutExpired, ProcessExecutionError
        """
        pass
```

---

## 4. `sse` 도메인 컴포넌트 메서드

### SSEConnectionManager

```python
class SSEConnectionManager:
    async def write_event_log(self, job_id: UUID, event_type: str, message: str) -> int:
        """
        Job 실행 과정 중 발생한 이벤트를 PostgreSQL DB에 INSERT하고 생성된 순차 ID를 반환합니다.
        - Input:
          - job_id (UUID)
          - event_type (str) - "log", "status_change", "artifact_created" 등
          - message (str) - 메시지 본문
        - Output: int - 데이터베이스에 기록된 Event Log 고유 순차 ID
        """
        pass

    async def stream_logs(self, job_id: UUID, last_event_id: int = None) -> AsyncGenerator[SSEEventSchema, None]:
        """
        클라이언트 연결 시, 실시간 로그 스트림을 비동기 제너레이터 형태로 전달합니다.
        Last-Event-ID 수신 시, 누락 로그를 먼저 SQL로 복구 조회하여 전달한 뒤 실시간 폴링 스트림으로 전환합니다.
        - Input:
          - job_id (UUID)
          - last_event_id (int, optional) - 클라이언트가 제시한 마지막 이벤트 번호
          - polling_interval (float) - 0.5초 간격 SQL 조회 폴링 주기
        - Output: AsyncGenerator[SSEEventSchema, None] - SSE 포맷에 맞춘 이벤트 스트림
        """
        pass
```

---

## 5. `storage` 도메인 컴포넌트 메서드

### StorageService (Interface)

```python
class StorageService(ABC):
    @abstractmethod
    def initialize_workspace(self, job_id: UUID) -> Path:
        """
        Job 전용의 빈 임시 작업 공간(Workspace 디렉토리)을 물리적으로 생성 및 확보합니다.
        - Input: job_id (UUID)
        - Output: Path - 생성된 Workspace의 절대 경로
        """
        pass

    @abstractmethod
    def store_job_artifact(self, job_id: UUID, file_name: str, content: bytes) -> str:
        """
        완성된 Artifact 파일을 영구 저장소에 이동/저장하고 이를 조회/다운로드할 수 있는 고유 URL을 반환합니다.
        - Input:
          - job_id (UUID)
          - file_name (str) - 예: "preview.png"
          - content (bytes) - 파일 바이너리
        - Output: str - 파일 다운로드 Endpoint URL
        """
        pass

    @abstractmethod
    def clean_workspace(self, job_id: UUID) -> None:
        """
        작업이 종료된 Job의 임시 작업 공간(Workspace) 내 불필요한 리소스를 정리합니다.
        - Input: job_id (UUID)
        - Output: None
        """
        pass
```
