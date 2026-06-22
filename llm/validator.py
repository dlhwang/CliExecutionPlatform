import uuid
from pathlib import Path
from typing import List
from sqlalchemy.orm import Session
from llm.schemas import ActionType
from llm.parser import LLMPlanValidationError
from jobs.models import EventLog

class SecurityPolicyValidator:
    """
    액션 플랜 내 개별 액션들의 보안 위반 요소(상대/절대 경로 탐색, 심볼릭링크, 허용 툴 외 구동)를
    정밀하게 검증하고, 정책 위반 감지 시 즉각 DB event_logs 테이블에 동기식 감사 로그를 기록하는 검증기 클래스입니다.
    """
    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            # 기본값으로 프로젝트 루트/.workspaces 폴더 지정
            self.base_dir = Path(__file__).parent.parent.resolve() / ".workspaces"
        else:
            self.base_dir = Path(base_dir).resolve()

    def validate_actions(self, actions: List[ActionType], job_id: uuid.UUID, db: Session) -> None:
        """
        전체 액션 플랜의 보안 제약 사항(Path Traversal, Symlink 우회, 비인가 도구)을 검증합니다.
        위반 발생 시 즉시 DB에 보안 감사 로그를 동기적으로 적재하고 예외를 던집니다.

        - Parameter:
          - actions: 검증 대상 액션 인스턴스 리스트
          - job_id: 실행 대상 Job의 UUID
          - db: 동기식 감사 로그 기록을 수행할 데이터베이스 세션
        - Exception:
          - LLMPlanValidationError: 보안 규칙 위반 감지 시 (Status Code 403 / FORBIDDEN_ACCESS)
        """
        base_job_dir = (self.base_dir / "jobs" / str(job_id)).resolve()

        for action_obj in actions:
            action_type = action_obj.action

            # 1. 외부 도구 화이트리스트 검증 (RUN_TOOL 액션)
            if action_type == "RUN_TOOL":
                tool_name = action_obj.tool_name.lower().strip()
                if tool_name != "openscad":
                    err_msg = f"Access denied. Security policy violation: Unauthorized tool: {action_obj.tool_name}"
                    self._log_and_raise_violation(db, job_id, err_msg)

            # 2. 경로 관련 제약 조건 검증 (CREATE_DIRECTORY, WRITE_FILE, CREATE_ARTIFACT 액션)
            elif action_type in ("CREATE_DIRECTORY", "WRITE_FILE", "CREATE_ARTIFACT"):
                path_str = action_obj.path

                # 2.1 상대경로 상위 디렉토리 침투 차단 (Path Traversal 방지)
                if "../" in path_str or "..\\" in path_str:
                    err_msg = f"Access denied. Security policy violation: Path traversal attempt detected: {path_str}"
                    self._log_and_raise_violation(db, job_id, err_msg)

                # 2.2 절대경로 차단
                if path_str.startswith("/") or path_str.startswith("\\") or Path(path_str).is_absolute():
                    err_msg = f"Access denied. Security policy violation: Absolute path not allowed: {path_str}"
                    self._log_and_raise_violation(db, job_id, err_msg)

                # 2.3 물리 작업 영역 영역 하위 준수 검증 (Path Resolve Bound)
                target_path = (base_job_dir / path_str).resolve()
                
                is_safe = False
                try:
                    if hasattr(target_path, "is_relative_to"):
                        is_safe = target_path.is_relative_to(base_job_dir)
                    else:
                        target_path.relative_to(base_job_dir)
                        is_safe = True
                except ValueError:
                    is_safe = False

                if not is_safe:
                    err_msg = f"Access denied. Security policy violation: Path is not relative to the workspace: {path_str}"
                    self._log_and_raise_violation(db, job_id, err_msg)

                # 2.4 심볼릭 링크 검증 (WRITE_FILE, CREATE_ARTIFACT 액션)
                # 실제 로컬 디스크 상에 파일이 이미 존재하고 있으며, 그 경로 상에 심볼릭링크가 포함되어 있는 경우 차단
                if action_type in ("WRITE_FILE", "CREATE_ARTIFACT"):
                    raw_target_path = base_job_dir / path_str
                    current = raw_target_path
                    while current != base_job_dir and current != current.parent:
                        if current.is_symlink():
                            err_msg = f"Access denied. Security policy violation: Symbolic link detected: {path_str}"
                            self._log_and_raise_violation(db, job_id, err_msg)
                        current = current.parent

                # 2.5 Scad 파일 내용에 대한 정적 검증 (WRITE_FILE 액션 및 .scad 확장자 대상)
                if action_type == "WRITE_FILE" and path_str.lower().endswith(".scad"):
                    from llm.scad_validator import ScadStaticValidator
                    ScadStaticValidator.validate(action_obj.content)


    def _log_and_raise_violation(self, db: Session, job_id: uuid.UUID, message: str) -> None:
        """
        보안 위반 내용을 DB event_logs 테이블에 동기적으로 INSERT하고 403 예외를 던집니다.
        """
        # 동기식 데이터베이스 적재 (감사 무결성 보장)
        audit_log = EventLog(
            job_id=job_id,
            event_type="SECURITY_ALERT",
            message=message
        )
        db.add(audit_log)
        db.commit()

        # 즉시 실패를 위해 LLMPlanValidationError 예외 발생
        raise LLMPlanValidationError(
            message=message,
            status_code=403,
            error_code="FORBIDDEN_ACCESS"
        )
