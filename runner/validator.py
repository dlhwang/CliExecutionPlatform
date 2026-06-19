"""
runner/validator.py

CLI 실행 인자(arguments)에 대한 Allowlist 기반 보안 검증기.

NFR-1.4 (Shell Injection 방지) 및 NFR Design Q3 결정(C - Allowlist 방식)을 구현합니다.
shell=False 사용과 함께 이 검증기를 반드시 거쳐야만 프로세스가 실행됩니다.
"""
import re
from typing import List

from runner.exceptions import CLIArgumentValidationError


class ArgumentValidator:
    """
    CLI 실행 인자 목록을 허용 패턴(Allowlist 정규식)과 대조하여 위험 인자를 실행 전에 차단합니다.

    허용 문자 범위:
        영문 대소문자 (a-zA-Z), 숫자 (0-9), 그리고 다음 특수문자만 허용합니다:
          '.', '/', ':', '_', '-', '=', ','

    차단 예시:
        - 'output.png; rm -rf /'     → ';' 포함으로 차단
        - '$(evil_command)'          → '$', '(' 포함으로 차단
        - 'file.scad | tee /etc'     → '|' 포함으로 차단
        - '../etc/passwd'            → (경로 검증은 SecurityPolicyValidator 담당)

    통과 예시:
        - '-o'
        - 'output.png'
        - 'model.scad'
        - '--render'
        - '-D=SIZE=10'
    """

    # Allowlist 정규식: 허용된 문자만으로 구성된 인자만 통과
    # 영문자, 숫자, 점, 슬래시(경로), 콜론, 언더스코어, 하이픈, 등호, 쉼표
    SAFE_ARG_PATTERN: re.Pattern = re.compile(r'^[a-zA-Z0-9_./:=,\-]+$')

    @classmethod
    def validate(cls, args: List[str]) -> None:
        """
        인자 목록의 각 요소를 SAFE_ARG_PATTERN으로 검사합니다.
        허용 패턴에 매칭되지 않는 인자가 하나라도 발견되면 즉시 CLIArgumentValidationError를 발생시킵니다.

        Args:
            args: CLI 실행에 전달될 인자 문자열 목록 (바이너리 경로 제외)

        Raises:
            CLIArgumentValidationError: Allowlist 정규식에 매칭되지 않는 인자가 발견된 경우

        Examples:
            >>> ArgumentValidator.validate(["-o", "output.png", "model.scad"])  # 통과
            >>> ArgumentValidator.validate(["model.scad; cat /etc/passwd"])      # 차단
        """
        for arg in args:
            if not cls.SAFE_ARG_PATTERN.match(arg):
                raise CLIArgumentValidationError(offending_arg=arg)
