# 비즈니스 규칙 및 검증 규칙서 (Business Rules & Validation) - Unit 3: CLI Runner Service

본 문서는 **Unit 3: CLI Runner Service**의 서브프로세스 기동 제약 조건, 아규먼트 보안 정합성 검사 규칙, 예외 발생 시 에러 코드 매핑 정책을 정의합니다.

---

## 1. CLI 프로세스 보안 및 가동 규칙 (Process Security Rules)

플랫폼의 안정성과 보안 위협 방지를 위해 OpenSCAD CLI 호출 시 강제 준수해야 하는 제약 사항입니다.

| 검증 영역 | 상세 제약 조건 (Validation Constraints) | 대응 조치 및 예외 |
| :--- | :--- | :--- |
| **Shell Injection 방어** | subprocess 호출 시 `shell=True` 인자 사용을 절대 금지합니다. 모든 인자는 문자열 리스트(`List[str]`) 형태로 프로세스에 직접 매핑되어야 합니다. | 위반 시 호출 금지<br/>(`CLIExecutionError`) |
| **타임아웃(30초) 강제** | 툴 실행 개시 시점으로부터 최대 생존 한도를 30초로 제한합니다. 30초 경과 시 즉시 OS 프로세스 신호를 통해 가용 자원을 회수합니다. | 프로세스 강제 킬 및<br/>`CLIExecutionTimeoutError` 유발 |
| **실행 파일 검증** | 지정된 `OPENSCAD_BIN_PATH` 혹은 기본 명령어 `"openscad"` 실행 파일이 호스트 파일시스템 상에 정상 존재하거나 가용(Executable)한 상태여야 합니다. | 기동 불가 시<br/>`CLIExecutionError` 발생 |
| **아규먼트 포맷 제한** | LLM Action Plan에 수록된 `args` 항목 내에서 쉘 제어 특수문자(`|`, `;`, `&`, `>`, `<` 등)의 사용이 불필요하므로, 쉘 메타문자가 섞인 아규먼트는 실행 전 차단합니다. | 실행 거절 및<br/>`CLIExecutionError` 발생 |

---

## 2. 에러 핸들링 및 예외 클래스 규격 (Error Classification)

비동기 서브프로세스 기동 중 발생할 수 있는 이상 징후에 대한 커스텀 비즈니스 예외 구조입니다.

### 2.1 커스텀 예외 계층 구조
```text
Exception (Base Python Exception)
 └── CLIExecutionError (기본 CLI 실행 이상 예외)
      ├── CLIExecutionTimeoutError (실행 타임아웃 초과: 30초 한계 도달)
      └── CLIExecutionLaunchError (프로세스 기동 불가: 파일 부재 또는 실행 권한 오류)
```

### 2.2 예외별 속성 정의 및 에러 메시지 매핑
1. **`CLIExecutionLaunchError`**:
   - **발생 시점**: 지정된 OpenSCAD 실행 파일 경로가 잘못되었거나 실행 권한이 부족하여 `asyncio.create_subprocess_exec` 기동 시점에 `FileNotFoundError` 또는 `PermissionError`가 발생한 경우.
   - **전달 메시지**: `"Failed to launch OpenSCAD CLI. Executable not found or permission denied at: [PATH]"`
2. **`CLIExecutionTimeoutError`**:
   - **발생 시점**: OpenSCAD 실행 프로세스가 30초 이내에 정상 종료되지 않고, `asyncio.wait_for` 타임아웃 제한에 도달한 경우.
   - **전달 메시지**: `"OpenSCAD tool execution timed out after 30 seconds. Process terminated."`
3. **`CLIExecutionError`**:
   - **발생 시점**: 프로세스가 종료되었으나 Exit Code가 0이 아닌 비정상 종료 값(예: 1 또는 139)인 경우.
   - **전달 메시지**: `"OpenSCAD tool execution failed with exit code [CODE]."`
   - **전달 속성**: `exit_code: int`
