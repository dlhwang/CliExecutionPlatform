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


def test_scad_static_validation_rejects_vector_property_access():
    from llm.scad_validator import ScadStaticValidator
    # v.x, v.y, v.z 같은 속성 접근은 차단되어야 함
    content = "cube([10, 20, 30]);\nvector = [1, 2, 3];\necho(vector.x);"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_VECTOR_PROPERTY_ACCESS]" in exc_info.value.message


def test_scad_static_validation_rejects_single_quotes():
    from llm.scad_validator import ScadStaticValidator
    # 싱글 쿼트(') 차단 검증
    content = "cube([10, 20, 30]);\ntext('hello');"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_SINGLE_QUOTE]" in exc_info.value.message


def test_scad_static_validation_rejects_180_div_pi():
    from llm.scad_validator import ScadStaticValidator
    # 180 / PI 차단 검증
    content = "cube([10, 20, 30]);\nangle = atan2(1, 1) * 180 / PI;"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_RADIAN_CONVERSION]" in exc_info.value.message


def test_scad_static_validation_rejects_pi_div_180():
    from llm.scad_validator import ScadStaticValidator
    # PI / 180 차단 검증
    content = "cube([10, 20, 30]);\nangle = 45 * PI / 180;"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_RADIAN_CONVERSION]" in exc_info.value.message


def test_scad_static_validation_rejects_markdown_fence():
    from llm.scad_validator import ScadStaticValidator
    # 마크다운 코드 펜스 ``` 차단 검증
    content = "```openscad\ncube([10, 20, 30]);\n```"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_MARKDOWN_FENCE]" in exc_info.value.message


def test_scad_static_validation_rejects_prose():
    from llm.scad_validator import ScadStaticValidator
    # prose 설명글 차단 검증
    content = "Here is the code for the dice:\ncube([10, 20, 30]);"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_PROSE]" in exc_info.value.message


def test_scad_static_validation_rejects_empty_file():
    from llm.scad_validator import ScadStaticValidator
    # 빈 파일 차단 검증
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate("")
    assert "[SCAD_EMPTY_FILE]" in exc_info.value.message


def test_scad_static_validation_rejects_missing_scad_keyword():
    from llm.scad_validator import ScadStaticValidator
    # 키워드 없음 차단 검증
    content = "a = 1;\nb = 2;"
    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
    assert "[SCAD_MISSING_KEYWORD]" in exc_info.value.message


def test_scad_static_validation_accepts_valid_scad():
    from llm.scad_validator import ScadStaticValidator
    # 정상 스캐드 허용 검증
    content = 'cube([10, 20, 30]);\ntranslate([1, 2, v[0]]) sphere(d=10);\ntext("hello");'
    # 예외가 발생하지 않아야 함
    ScadStaticValidator.validate(content)


def test_scad_static_validation_ignores_comment_only_forbidden_patterns():
    from llm.scad_validator import ScadStaticValidator
    # 주석 내부의 금지 구문 무시 검증 (예: // v.x 또는 /* text('hello') */)
    content = """
    // v.x
    /* 
       text('hello') 
       Here is
       180 / PI
    */
    cube([10, 20, 30]);
    """
    # 주석이 제거된 뒤에는 cube 키워드만 남고 금지 구문은 없어야 하므로 예외가 발생하지 않아야 함
    ScadStaticValidator.validate(content)


def test_scad_static_validation_ignores_syntax_patterns_in_double_quoted_strings():
    from llm.scad_validator import ScadStaticValidator

    content = '''
    cube([10, 20, 30]);
    echo("point.x and 180 / PI and PI / 180 and Here is");
    text("escaped quote: \\" vector.y");
    '''
    ScadStaticValidator.validate(content)


def test_scad_static_validation_preserves_original_line_numbers_after_masking():
    from llm.scad_validator import ScadStaticValidator, strip_comments

    content = '''// vector.x
/* 180 / PI
   vector.y */
echo("vector.z and PI / 180");
cube([1, 1, 1]);
value = point.x;'''

    assert len(strip_comments(content)) == len(content)
    assert strip_comments(content).count("\n") == content.count("\n")

    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)

    message = exc_info.value.message
    assert "[SCAD_VECTOR_PROPERTY_ACCESS]" in message
    assert "Line 6: value = point.x;" in message
    assert "Line 1:" not in message
    assert content not in message


def test_scad_validation_feedback_does_not_include_full_content():
    from llm.scad_validator import ScadStaticValidator

    # 100줄이 넘고, 중간 52라인에만 위반이 심어진 긴 scad content 구성
    lines = []
    for i in range(1, 120):
        if i == 52:
            lines.append("vector = [1, 2, 3]; val = vector.x; // Forbidden rule 3")
        elif i == 80:
            lines.append("cube([5, 5, 5]); // Normal cube but normal code")
        else:
            lines.append(f"// Line {i} dummy content to inflate size translate([0, 0, 0])")
    
    # scad 키워드가 최소 1개 필요하므로 맨 끝에 module 추가
    lines.append("module dummy() { cube([1,1,1]); }")
    content = "\n".join(lines)

    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)
        
    msg = exc_info.value.message
    # 1. 전체 원본 content가 포함되어선 안 된다.
    # 즉, 100줄의 더미 주석 라인들이 피드백에 노출되지 않아야 한다.
    assert "dummy content to inflate size" not in msg
    # 2. 위반이 발생한 52라인의 snippet은 포함되어야 한다.
    assert "[SCAD_VECTOR_PROPERTY_ACCESS]" in msg
    assert "Line 52: vector = [1, 2, 3]; val = vector.x;" in msg
    # 3. 80라인의 정상 코드 라인 역시 피드백에 포함되지 않아야 한다.
    assert "Normal cube but normal code" not in msg


def test_scad_validation_feedback_is_bounded():
    from llm.scad_validator import ScadStaticValidator

    # 다수의 위반 사항을 중복으로 대량 심은 scad 코드 생성
    lines = []
    # 1. Markdown fence (Rule 2)
    # Markdown fence 라인도 150자가 넘게 구성
    lines.append("```scad " + ("f" * 150))
    
    # 2. Vector property access (Rule 3)
    for i in range(10):
        # snippet 길이 150자 제한 검증을 위해 150자가 넘는 아주 긴 위반 라인 삽입
        long_line = f"v.x = {i}; " + ("a" * 150) + " // very long padding line"
        lines.append(long_line)
        
    # 3. Single quotes (Rule 4)
    for i in range(10):
        # snippet 150자 초과를 위해 긴 라인 구성
        lines.append(f"s{i} = 'single quote string' " + ("b" * 150) + ";")
        
    # 4. Radian conversions (Rule 5)
    for i in range(10):
        lines.append(f"ang{i} = 180 / PI; " + ("c" * 150) + " // radian conversion")
        
    # 5. Prose explanations (Rule 6)
    for i in range(10):
        lines.append(f"// Here is some explanation {i}")
        lines.append(f"Here is some forbidden conversational prefix {i} " + ("d" * 150))

    lines.append("```")
    # 키워드 추가
    lines.append("module trigger() { cube([1,1,1]); }")

    content = "\n".join(lines)

    with pytest.raises(LLMPlanValidationError) as exc_info:
        ScadStaticValidator.validate(content)

    msg = exc_info.value.message
    
    # 1. 전체 메시지 길이는 1,500자를 넘을 수 없다.
    assert len(msg) <= 1500
    
    # 2. 생략되었다는 요약 문구가 포함되어야 한다.
    assert "[additional violations omitted]" in msg
    
    # 3. 대표 Rule ID는 여전히 일부 살아남아 에러 피드백의 정체성을 알리고 있어야 한다.
    assert "[SCAD_MARKDOWN_FENCE]" in msg
    assert "[SCAD_VECTOR_PROPERTY_ACCESS]" in msg
    
    # 4. snippet 150자 초과 시 truncate 되어 '...'이 붙어 있어야 한다.
    assert "..." in msg


def test_artifact_registration_accepts_valid_paths(db_session, test_storage):
    from jobs.service import ArtifactService
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    test_storage.create_workspace(job_id)
    test_storage.write_file(job_id, "models/model.scad", "cube([10, 20, 30]);")

    artifact_service = ArtifactService(db_session, test_storage)
    artifact = artifact_service.register_artifact(job_id, "models/model.scad")
    
    assert artifact.job_id == job_id
    assert artifact.relative_path == "models/model.scad"
    assert artifact.filename == "model.scad"
    assert "scad" in artifact.content_type or "octet-stream" in artifact.content_type


def test_artifact_registration_rejects_absolute_paths(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.register_artifact(job_id, "/etc/passwd")
    assert "Absolute paths are not allowed" in str(exc_info.value)


def test_artifact_registration_rejects_traversal_segments(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    for path in ("../file.txt", "dir/../../file.txt", "dir/./file.txt", "dir//file.txt"):
        with pytest.raises(ArtifactPermissionError) as exc_info:
            artifact_service.register_artifact(job_id, path)
        assert "Invalid path segments" in str(exc_info.value) or "Empty path" in str(exc_info.value)


def test_artifact_registration_rejects_windows_backslash(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.register_artifact(job_id, "models\\model.scad")
    assert "Windows backslashes are not allowed" in str(exc_info.value)


def test_artifact_download_success(db_session, test_storage):
    from jobs.service import ArtifactService
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    test_storage.create_workspace(job_id)
    test_storage.write_file(job_id, "output.stl", "stl content")

    artifact_service = ArtifactService(db_session, test_storage)
    artifact = artifact_service.register_artifact(job_id, "output.stl")
    db_session.commit()

    file_path, content_type, filename = artifact_service.get_artifact_for_download(artifact.id)
    assert file_path.exists()
    assert filename == "output.stl"
    assert content_type == "application/octet-stream" or "sla" in content_type


def test_artifact_download_404_unknown_id(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactNotFoundError
    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactNotFoundError) as exc_info:
        artifact_service.get_artifact_for_download(uuid.uuid4())
    assert "Artifact not found" in str(exc_info.value)


def test_artifact_download_404_missing_physical_file(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactNotFoundError
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    artifact = artifact_service.register_artifact(job_id, "missing.png")
    db_session.commit()

    with pytest.raises(ArtifactNotFoundError) as exc_info:
        artifact_service.get_artifact_for_download(artifact.id)
    assert "Physical file not found" in str(exc_info.value)


def test_artifact_download_404_not_regular_file(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactNotFoundError
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    test_storage.create_workspace(job_id)
    test_storage.create_directory(job_id, "sub_dir")

    artifact_service = ArtifactService(db_session, test_storage)
    # 물리적 검증을 위해 artifacts로 우회 등록 대신 register_artifact를 사용합니다.
    # 단, register_artifact 시점에는 물리 디렉토리가 workspace root 하위에 실제로 존재해야 resolve가 가능합니다.
    artifact = artifact_service.register_artifact(job_id, "sub_dir")
    db_session.commit()

    with pytest.raises(ArtifactNotFoundError) as exc_info:
        artifact_service.get_artifact_for_download(artifact.id)
    assert "not a regular file" in str(exc_info.value)


def test_artifact_download_403_traversal(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    from jobs.models import Artifact
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    # DB에 traversal 경로가 주입된 것으로 모의
    artifact = Artifact(
        job_id=job_id,
        relative_path="dir/../../file.txt",
        filename="file.txt",
        content_type="text/plain"
    )
    db_session.add(artifact)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.get_artifact_for_download(artifact.id)
    assert "Invalid path segments" in str(exc_info.value)


def test_artifact_download_403_absolute(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    from jobs.models import Artifact
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact = Artifact(
        job_id=job_id,
        relative_path="/absolute/path/file.txt",
        filename="file.txt",
        content_type="text/plain"
    )
    db_session.add(artifact)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.get_artifact_for_download(artifact.id)
    assert "Absolute paths are not allowed" in str(exc_info.value)


def test_artifact_download_403_prefix_bypass(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    from jobs.models import Artifact
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact = Artifact(
        job_id=job_id,
        relative_path=f"../{job_id}_evil/file.txt",
        filename="file.txt",
        content_type="text/plain"
    )
    db_session.add(artifact)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.get_artifact_for_download(artifact.id)
    assert "Invalid path segments" in str(exc_info.value)


def test_artifact_download_403_symlink_escape(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    from jobs.models import Artifact
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    test_storage.create_workspace(job_id)
    jobs_dir = test_storage.base_dir / "jobs" / str(job_id)
    
    # 샌드박스 밖의 파일
    outside_file = test_storage.base_dir / "outside_secret.txt"
    outside_file.write_text("secret info")
    
    symlink_path = jobs_dir / "secret_symlink.txt"
    try:
        symlink_path.symlink_to(outside_file)
    except OSError:
        pytest.skip("Symlink creation not allowed in this environment")

    # DB에는 relative_path="secret_symlink.txt" 로 정상적인 상대경로처럼 등록
    artifact = Artifact(
        job_id=job_id,
        relative_path="secret_symlink.txt",
        filename="secret_symlink.txt",
        content_type="text/plain"
    )
    db_session.add(artifact)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.get_artifact_for_download(artifact.id)
    assert "Path traversal attempt detected" in str(exc_info.value)


def test_artifact_download_no_server_path_disclosure(db_session, test_storage):
    from jobs.service import ArtifactService, ArtifactPermissionError
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Test prompt", status="RUNNING")
    db_session.add(job)
    db_session.commit()

    artifact_service = ArtifactService(db_session, test_storage)
    
    # 1. 403 예외 메시지 절대경로 차단 검증
    with pytest.raises(ArtifactPermissionError) as exc_info:
        artifact_service.register_artifact(job_id, "/etc/passwd")
    err_msg = str(exc_info.value)
    assert "etc" not in err_msg
    assert "passwd" not in err_msg
    # 절대경로 조각이 직접 유출되지 않는지 확인
    assert "etc/passwd" not in err_msg
    assert "etc\\passwd" not in err_msg


def test_get_artifacts_success(client, db_session, test_storage):
    """
    R-17: 완료(COMPLETED) 상태인 Job에 연계된 아티팩트 목록이 정상적으로 반환되는가?
    응답에는 id, filename, content_type, created_at만 포함되고 relative_path는 없어야 한다.
    """
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="주사위 만들기", status="COMPLETED")
    db_session.add(job)
    db_session.commit()

    test_storage.create_workspace(job_id)
    test_storage.write_file(job_id, "output.stl", "stl_content")

    from jobs.service import ArtifactService
    artifact_service = ArtifactService(db_session, test_storage)
    artifact = artifact_service.register_artifact(job_id, "output.stl")
    db_session.commit()

    response = client.get(f"/api/v1/jobs/{job_id}/artifacts")
    assert response.status_code == 200
    
    data = response.json()
    assert len(data) == 1
    assert data[0]["id"] == str(artifact.id)
    assert data[0]["filename"] == "output.stl"
    assert data[0]["content_type"] == "application/octet-stream"
    assert "created_at" in data[0]
    assert "relative_path" not in data[0]  # 보안상 차단 검증


def test_get_artifacts_not_found(client):
    """
    R-17: 존재하지 않는 job_id 조회 시 404 Not Found를 반환하는가?
    """
    random_job_id = uuid.uuid4()
    response = client.get(f"/api/v1/jobs/{random_job_id}/artifacts")
    assert response.status_code == 404
    
    data = response.json()
    assert data["detail"]["code"] == "NOT_FOUND"
    assert "not found" in data["detail"]["message"].lower()


def test_get_artifacts_not_completed(client, db_session):
    """
    R-17: Job 상태가 COMPLETED가 아닐 때 (CREATED, RUNNING, FAILED) 400 Bad Request를 반환하는가?
    """
    for status in ("CREATED", "RUNNING", "FAILED"):
        job_id = uuid.uuid4()
        job = Job(id=job_id, prompt="작업용", status=status)
        db_session.add(job)
        db_session.commit()

        response = client.get(f"/api/v1/jobs/{job_id}/artifacts")
        assert response.status_code == 400
        
        data = response.json()
        assert data["detail"]["code"] == "BAD_REQUEST"
        assert "completed" in data["detail"]["message"].lower()


