import uuid
import pytest
from pathlib import Path
from sqlalchemy.orm import Session
from llm.parser import ActionPlanParser, LLMPlanRetryableException, LLMPlanValidationError
from llm.validator import SecurityPolicyValidator
from llm.schemas import CreateDirectoryAction, WriteFileAction, RunToolAction, CreateArtifactAction
from jobs.models import Job, EventLog

def test_json_extraction_success():
    """
    Markdown 내 JSON 추출 성공 검증:
    1) ```json ... ``` 형태의 마크다운 코드 블록 파싱 성공 검증.
    2) 코드 블록 없이 첫 [와 마지막 ] 사이에 JSON이 섞인 텍스트 파싱 성공 검증.
    """
    parser = ActionPlanParser()
    
    # 1) 마크다운 코드 블록 형태 파싱 검증
    raw_markdown = """
어시스턴트: 다음과 같이 실행 계획을 구성했습니다.
```json
{
  "plan": [
    {
      "action": "CREATE_DIRECTORY",
      "path": "test_dir"
    },
    {
      "action": "WRITE_FILE",
      "path": "test_dir/model.scad",
      "content": "cube([10, 20, 30]);"
    }
  ]
}
```
도킹 스테이션 모델링 준비를 마쳤습니다.
"""
    actions = parser.parse_action_plan(raw_markdown)
    assert len(actions) == 2
    assert isinstance(actions[0], CreateDirectoryAction)
    assert actions[0].path == "test_dir"
    assert isinstance(actions[1], WriteFileAction)
    assert actions[1].path == "test_dir/model.scad"
    assert actions[1].content == "cube([10, 20, 30]);"

    # 2) Fallback 처리: 첫 '[' 와 마지막 ']' 문자 범위 추출 검증
    raw_text_fallback = """
여기 액션 플랜을 제안합니다:
[
  {
    "action": "RUN_TOOL",
    "tool_name": "openscad",
    "args": ["-o", "output.png", "test_dir/model.scad"]
  }
]
위의 명령을 실행해 주세요.
"""
    actions_fallback = parser.parse_action_plan(raw_text_fallback)
    assert len(actions_fallback) == 1
    assert isinstance(actions_fallback[0], RunToolAction)
    assert actions_fallback[0].tool_name == "openscad"
    assert actions_fallback[0].args == ["-o", "output.png", "test_dir/model.scad"]


def test_parser_retryable_exception():
    """
    JSON 구문 문법 오류 시 재시도 예외 검증:
    괄호 누락 등 문법이 깨진 JSON 응답 주입 시 LLMPlanRetryableException 발생 검증.
    """
    parser = ActionPlanParser()
    
    bad_json_raw = """
```json
{
  "plan": [
    {
      "action": "CREATE_DIRECTORY",
      "path": "test_dir"
    // 문법 오류 고의 발생: 콤마 및 대괄호 누락
  ]
}
```
"""
    with pytest.raises(LLMPlanRetryableException) as exc_info:
        parser.parse_action_plan(bad_json_raw)
        
    err = exc_info.value
    assert "Syntax error" in err.message or "Failed to parse" in err.message
    assert err.raw_content == bad_json_raw
    assert err.error_position is not None
    assert "line" in err.error_position or "col" in err.error_position


def test_parser_validation_exception():
    """
    Pydantic 스키마 검증 실패 검증:
    action 명 오타 및 필수 필드 누락 시 LLMPlanValidationError 예외 유발 검증.
    """
    parser = ActionPlanParser()
    
    # 잘못된 action 타입명 주입 (CREATE_DIR)
    bad_action_type = """
```json
[
  {
    "action": "CREATE_DIR",
    "path": "test_dir"
  }
]
```
"""
    with pytest.raises(LLMPlanValidationError) as exc_info:
        parser.parse_action_plan(bad_action_type)
    assert "validation failed" in exc_info.value.message.lower()

    # 필수 필드 path 누락
    missing_field = """
```json
[
  {
    "action": "CREATE_DIRECTORY"
  }
]
```
"""
    with pytest.raises(LLMPlanValidationError) as exc_info:
        parser.parse_action_plan(missing_field)
    assert "validation failed" in exc_info.value.message.lower()


def test_security_validator_path_protection(db_session, test_storage):
    """
    경로 침투 및 심볼릭링크 차단과 DB 감사 적재 검증:
    1) ../ 및 ..\\ 상대경로 이탈 시도 시 차단 및 DB 적재 검증.
    2) 절대경로 사용 시 차단 및 DB 적재 검증.
    3) 물리 영역(Workspace) 이탈 검증.
    4) 심볼릭링크 탐색 시 차단 및 DB 적재 검증.
    """
    # 1. Job 더미 데이터 적재 (Foreign Key 일관성 준수)
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    # Validator를 임시 storage의 base_dir로 초기화
    validator = SecurityPolicyValidator(base_dir=test_storage.base_dir)

    # 1) Traversal 경로 침투 검출
    traversal_action = [CreateDirectoryAction(action="CREATE_DIRECTORY", path="../outside_dir")]
    with pytest.raises(LLMPlanValidationError) as exc_info:
        validator.validate_actions(traversal_action, job_id, db_session)
    
    assert exc_info.value.status_code == 403
    assert "Path traversal attempt detected" in exc_info.value.message

    # DB event_logs 테이블에 SECURITY_ALERT 로그 적재 검증
    log = db_session.query(EventLog).filter_by(job_id=job_id, event_type="SECURITY_ALERT").first()
    assert log is not None
    assert "Path traversal attempt detected" in log.message

    # 2) 절대경로 차단 검증
    absolute_action = [WriteFileAction(action="WRITE_FILE", path="/etc/passwd", content="malicious")]
    with pytest.raises(LLMPlanValidationError) as exc_info:
        validator.validate_actions(absolute_action, job_id, db_session)
    assert exc_info.value.status_code == 403
    assert "Absolute path not allowed" in exc_info.value.message

    # 3) 물리 영역 이탈 검증 (resolve 및 is_relative_to 활용)
    out_of_bound_action = [CreateDirectoryAction(action="CREATE_DIRECTORY", path="sub/../../outside")]
    with pytest.raises(LLMPlanValidationError) as exc_info:
        validator.validate_actions(out_of_bound_action, job_id, db_session)
    assert "is not relative to the workspace" in exc_info.value.message or "Path traversal attempt detected" in exc_info.value.message

    # 4) 심볼릭 링크 차단 검증
    test_storage.create_workspace(job_id)
    jobs_dir = test_storage.base_dir / "jobs" / str(job_id)
    
    real_file = jobs_dir / "real_file.txt"
    real_file.write_text("this is real")
    
    symlink_file = jobs_dir / "symlink_file.txt"
    try:
        symlink_file.symlink_to(real_file)
    except OSError:
        # Windows 개발 환경에서 심볼릭 링크 생성이 불가능한 로컬 정책인 경우 대비 Mocking/Skip 처리 지원
        # target_path.is_symlink 가 참으로 판정될 수 있도록 임의 mock/patch 할 수도 있으나 권한 존재 시에만 단독 수행
        pass

    if symlink_file.is_symlink():
        symlink_action = [WriteFileAction(action="WRITE_FILE", path="symlink_file.txt", content="hack")]
        with pytest.raises(LLMPlanValidationError) as exc_info:
            validator.validate_actions(symlink_action, job_id, db_session)
        assert "Symbolic link detected" in exc_info.value.message


def test_security_validator_tool_whitelist(db_session):
    """
    도구 화이트리스트 차단 검증:
    RUN_TOOL 액션 시 openscad 외에 비인가 툴(bash 등) 유입 시 차단 검증.
    """
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    validator = SecurityPolicyValidator()

    # 1) 허용되지 않은 툴 (bash) 차단 검증
    bad_tool_action = [RunToolAction(action="RUN_TOOL", tool_name="bash", args=["-c", "ls"])]
    with pytest.raises(LLMPlanValidationError) as exc_info:
        validator.validate_actions(bad_tool_action, job_id, db_session)
    assert exc_info.value.status_code == 403
    assert "Unauthorized tool" in exc_info.value.message

    # 2) 대소문자 무관 openscad 허용 검증
    good_tool_action = [RunToolAction(action="RUN_TOOL", tool_name="OpenSCAD", args=["model.scad"])]
    validator.validate_actions(good_tool_action, job_id, db_session)
