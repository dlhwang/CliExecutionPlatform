# 도메인 엔티티 정의서 (Domain Entities) - Unit 3: CLI Runner Service

본 문서는 **Unit 3: CLI Runner Service**의 컴포넌트 인터페이스 시그니처, 커스텀 예외 클래스 필드 규격, 그리고 데이터베이스 적재용 로그 엔티티 매핑 명세를 정의합니다.

---

## 1. 컴포넌트 메서드 및 예외 클래스 명세

### 1.1 `CLIExecutionRunner` 서비스 인터페이스 (runner/service.py)
* **메서드 정의**:
  ```python
  class CLIExecutionRunner:
      def __init__(self, base_dir: Path | str | None = None):
          """
          바이너리 경로 및 작업 영역 루트 경로를 초기화합니다.
          """
          pass

      async def run_tool(self, job_id: uuid.UUID, tool_name: str, args: List[str], db: Session) -> int:
          """
          비동기 서브프로세스를 생성하여 OpenSCAD CLI를 가동합니다.
          
          - Parameters:
            - job_id: 실행 대상 Job의 UUID (로그 테이블 외래키 매핑)
            - tool_name: 호출 도구명 (검증 통과한 openscad)
            - args: 도구 실행 아규먼트 리스트 (예: ["-o", "preview.png", "model.scad"])
            - db: 실시간 로그 영속화를 수행할 데이터베이스 동기식 세션
          - Return:
            - int: 프로세스의 최종 정상 Exit Code (0)
          - Exceptions:
            - CLIExecutionLaunchError: 바이너리 부재 또는 구동 실패 시
            - CLIExecutionTimeoutError: 30초 실행 제한 도달 시
            - CLIExecutionError: Non-zero Exit Code로 비정상 종료 시
          """
          pass
  ```

### 1.2 예외 클래스 멤버 필드 명세 (runner/exceptions.py)
* **`CLIExecutionError`**:
  - `message`: 구체적인 실패 사유 요약 (str)
  - `exit_code`: 서브프로세스가 반환한 비정상 종료 코드 (Optional[int])
* **`CLIExecutionLaunchError`**:
  - `message`: 기동 불가 사유 요약 (str)
  - `target_path`: 접근을 시도했던 실행 파일 경로 (str)
* **`CLIExecutionTimeoutError`**:
  - `message`: 타임아웃 종료 요약 (str)
  - `timeout_limit`: 설정된 최대 대기 제한 시간 (int - 30)

---

## 2. 데이터베이스 로그 엔티티 매핑 규격 (EventLog Mapping)

서브프로세스 stdout/stderr 실시간 출력이 데이터베이스 `event_logs` 테이블에 적재될 때 적용되는 필드 맵핑 테이블입니다. (질문 1: B - 비동기 라인 단위 실시간 기록 의사결정 반영)

| EventLog 컬럼 | 적재 값 (Value Mapping) | 데이터 타입 | 설명 |
| :--- | :--- | :--- | :--- |
| **id** | 자동 증분 (Primary Key) | BigInteger / Integer | 시스템에 의해 자동 생성되는 고유 식별 번호 |
| **job_id** | `job_id` | UUID | 실행 중인 비동기 CLI 작업의 부모 외래키 번호 |
| **event_type** | `"CLI_OUTPUT"` | String(50) | 프로세스 표준 출력을 나타내는 고정 지표 코드 |
| **message** | `line.decode("utf-8").strip()` | Text | 버퍼링 없이 한 라인씩 정제되어 디코딩 완료된 순수 로그 문자열 |
| **created_at** | `func.now()` | DateTime | 로그 레코드가 DB에 기록된 실시간 시점 |
