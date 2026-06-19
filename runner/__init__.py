"""
runner/__init__.py

CLI Runner Service 패키지.

공개 API:
    - CLIExecutionRunner: 핵심 실행 오케스트레이터
    - CLIExecutionError: 기본 CLI 실행 실패 예외
    - CLIExecutionLaunchError: 프로세스 기동 실패 예외
    - CLIExecutionTimeoutError: 30초 타임아웃 초과 예외
    - CLIArgumentValidationError: Allowlist 검증 실패 예외
"""
from runner.service import CLIExecutionRunner
from runner.exceptions import (
    CLIExecutionError,
    CLIExecutionLaunchError,
    CLIExecutionTimeoutError,
    CLIArgumentValidationError,
)

__all__ = [
    "CLIExecutionRunner",
    "CLIExecutionError",
    "CLIExecutionLaunchError",
    "CLIExecutionTimeoutError",
    "CLIArgumentValidationError",
]
