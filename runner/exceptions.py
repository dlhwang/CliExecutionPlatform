"""
runner/exceptions.py

CLI Runner Service의 커스텀 예외 계층 정의.

예외 계층:
    Exception
    └── RuntimeError
        ├── CLIExecutionError          기본 CLI 실행 실패 예외 (Exit Code 이상)
        │   ├── CLIExecutionLaunchError  프로세스 기동 실패 (재시도 초과)
        │   └── CLIExecutionTimeoutError 30초 타임아웃 초과
    └── ValueError
        └── CLIArgumentValidationError  Allowlist 검증 실패
"""
from typing import Optional


class CLIExecutionError(RuntimeError):
    """
    OpenSCAD 프로세스가 정상 기동 후 비정상 종료(Non-Zero Exit Code)되었을 때 발생하는 기본 예외.

    Attributes:
        message (str): 실패 사유 요약 메시지
        exit_code (Optional[int]): 프로세스가 반환한 비정상 종료 코드
    """
    def __init__(self, message: str, exit_code: Optional[int] = None) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code

    def __repr__(self) -> str:
        return f"CLIExecutionError(message={self.message!r}, exit_code={self.exit_code!r})"


class CLIExecutionLaunchError(CLIExecutionError):
    """
    asyncio.create_subprocess_exec 기동 시점에 OSError(FileNotFoundError, PermissionError 등)가
    최대 재시도 횟수(2회)를 초과하여 발생했을 때의 예외.

    Attributes:
        message (str): 기동 불가 사유 요약
        target_path (str): 접근을 시도했던 실행 파일 경로
        attempts (int): 실제 시도 횟수 (1~3)
    """
    def __init__(self, message: str, target_path: str, attempts: int) -> None:
        super().__init__(message, exit_code=None)
        self.target_path = target_path
        self.attempts = attempts

    def __repr__(self) -> str:
        return (
            f"CLIExecutionLaunchError("
            f"message={self.message!r}, "
            f"target_path={self.target_path!r}, "
            f"attempts={self.attempts!r})"
        )


class CLIExecutionTimeoutError(CLIExecutionError):
    """
    asyncio.wait_for의 30초 데드라인을 초과하여 프로세스가 강제 종료되었을 때 발생하는 예외.

    Attributes:
        message (str): 타임아웃 종료 요약
        timeout_limit (float): 설정된 최대 대기 제한 시간 (초 단위, 기본값 30.0)
    """
    def __init__(self, message: str, timeout_limit: float = 30.0) -> None:
        super().__init__(message, exit_code=None)
        self.timeout_limit = timeout_limit

    def __repr__(self) -> str:
        return (
            f"CLIExecutionTimeoutError("
            f"message={self.message!r}, "
            f"timeout_limit={self.timeout_limit!r})"
        )


class CLIArgumentValidationError(ValueError):
    """
    Allowlist 정규식에 매칭되지 않는 인자가 CLI 실행 목록에 포함된 경우 발생하는 예외.
    프로세스 실행 전 단계에서 즉시 차단됩니다.

    Attributes:
        offending_arg (str): 검증을 통과하지 못한 원본 인자 문자열
    """
    def __init__(self, offending_arg: str) -> None:
        message = (
            f"Argument validation failed: unsafe characters detected in argument: {offending_arg!r}. "
            f"Only alphanumerics, '.', '/', ':', '_', '-', '=', ',' are permitted."
        )
        super().__init__(message)
        self.offending_arg = offending_arg

    def __repr__(self) -> str:
        return f"CLIArgumentValidationError(offending_arg={self.offending_arg!r})"
