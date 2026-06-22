import asyncio
from datetime import datetime, timedelta, timezone
import logging
from uuid import UUID

import httpx
import pytest
from sqlalchemy.orm import Session
from uuid6 import uuid7

from jobs.models import EventLog, Job
from jobs.service import JobService
from llm.client import (
    HttpLLMClient,
    LLMClientError,
    LLMRequest,
    LLMResponseTooLargeError,
)
from llm.parser import ActionPlanParser
from llm.retry import LLMPlanRetryExecutor
from llm.validator import SecurityPolicyValidator
from orchestrator.actions import ActionExecutor
from orchestrator.concurrency import (
    OrchestrationConcurrencyGate,
    OrchestrationQueueTimeoutError,
)
from orchestrator.config import OrchestratorConfig, OrchestratorConfigurationError
from orchestrator.recovery import StaleJobRecoveryService
from orchestrator.repository import OrchestratorRepository
from orchestrator.service import JobOrchestratorService
from conftest import TestingSessionLocal


class FakeLLMClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.requests = []

    async def generate_plan(self, request):
        self.requests.append(request)
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeRunner:
    async def run_tool(self, job_id, tool_name, args, db, timeout_seconds=30.0):
        return 0


def _make_parent(db_session: Session, test_storage):
    parent = Job(id=uuid7(), prompt="parent", status="COMPLETED")
    db_session.add(parent)
    db_session.commit()
    test_storage.create_workspace(parent.id)
    test_storage.write_file(parent.id, "model.scad", "cube([1,1,1]);")
    test_storage.write_file(parent.id, "design-spec.md", "# Parent")
    return parent


def test_refinement_creates_child_job(client, db_session, test_storage):
    parent = _make_parent(db_session, test_storage)
    response = client.post(
        f"/api/v1/jobs/{parent.id}/refine",
        json={"prompt": "Add a cable hole"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["parent_job_id"] == str(parent.id)
    child = db_session.query(Job).filter(Job.id == UUID(data["id"])).one()
    assert child.status == "CREATED"


def test_refinement_rejects_invalid_parent_or_missing_files(client, db_session, test_storage):
    missing = client.post(f"/api/v1/jobs/{uuid7()}/refine", json={"prompt": "valid feedback"})
    assert missing.status_code == 404

    parent = Job(id=uuid7(), prompt="parent", status="RUNNING")
    db_session.add(parent)
    db_session.commit()
    conflict = client.post(f"/api/v1/jobs/{parent.id}/refine", json={"prompt": "valid feedback"})
    assert conflict.status_code == 409

    parent.status = "COMPLETED"
    db_session.commit()
    test_storage.create_workspace(parent.id)
    no_files = client.post(f"/api/v1/jobs/{parent.id}/refine", json={"prompt": "valid feedback"})
    assert no_files.status_code == 409


def test_refinement_rejects_context_over_five_mb(client, db_session, test_storage):
    parent = _make_parent(db_session, test_storage)
    test_storage.write_file(parent.id, "model.scad", b"x" * (5 * 1024 * 1024))
    response = client.post(f"/api/v1/jobs/{parent.id}/refine", json={"prompt": "valid feedback"})
    assert response.status_code == 413
    assert db_session.query(Job).filter(Job.parent_job_id == parent.id).count() == 0


def test_refinement_copies_context_and_calls_llm(db_session, test_storage):
    parent = _make_parent(db_session, test_storage)
    child = JobService(db_session, test_storage).create_job("refine prompt", parent.id)
    client = FakeLLMClient([
        '[{"action":"WRITE_FILE","path":"result.txt","content":"done"}]'
    ])
    repository = OrchestratorRepository(TestingSessionLocal)
    service = JobOrchestratorService(
        repository,
        TestingSessionLocal,
        test_storage,
        client,
        ActionPlanParser(),
        SecurityPolicyValidator(test_storage.base_dir),
        ActionExecutor(test_storage, FakeRunner(), TestingSessionLocal),
        OrchestrationConcurrencyGate(),
    )

    assert asyncio.run(service.run(child.id))
    assert test_storage.read_file(child.id, "model.scad") == b"cube([1,1,1]);"
    assert test_storage.read_file(child.id, "design-spec.md") == b"# Parent"
    assert test_storage.read_file(child.id, "result.txt") == b"done"
    assert client.requests[0].context["model.scad"] == "cube([1,1,1]);"
    db_session.expire_all()
    assert db_session.get(Job, child.id).status == "COMPLETED"


def test_job_state_transitions_and_duplicate_execution(db_session, test_storage):
    job = JobService(db_session, test_storage).create_job("initial prompt")
    client = FakeLLMClient(['[{"action":"WRITE_FILE","path":"a.txt","content":"a"}]'])
    service = JobOrchestratorService(
        OrchestratorRepository(TestingSessionLocal), TestingSessionLocal, test_storage,
        client, ActionPlanParser(), SecurityPolicyValidator(test_storage.base_dir),
        ActionExecutor(test_storage, FakeRunner(), TestingSessionLocal), OrchestrationConcurrencyGate(),
    )
    assert asyncio.run(service.run(job.id))
    assert not asyncio.run(service.run(job.id))
    assert len(client.requests) == 1


def test_llm_retry_classification_and_backoff():
    async def scenario():
        delays = []
        client = FakeLLMClient([
            LLMClientError("temporary", retryable=True),
            LLMClientError("temporary", retryable=True),
            '[]',
        ])

        async def sleep(delay):
            delays.append(delay)

        actions = await LLMPlanRetryExecutor(
            client, ActionPlanParser(), sleep=sleep
        ).generate_actions(LLMRequest("prompt", {}, ("WRITE_FILE",)))
        assert actions == []
        assert delays == [1.0, 2.0]

    asyncio.run(scenario())


def test_concurrency_gate_limits_two_jobs_and_times_out_waiter():
    async def scenario():
        gate = OrchestrationConcurrencyGate(max_concurrent=2, wait_timeout=0.01)
        async with gate.slot():
            async with gate.slot():
                with pytest.raises(OrchestrationQueueTimeoutError):
                    async with gate.slot():
                        pass
        async with gate.slot():
            pass

    asyncio.run(scenario())


def test_endpoint_security_and_secret_validation(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LLM_ENDPOINT", "http://example.com/llm")
    monkeypatch.setenv("LLM_API_KEY", "secret")
    monkeypatch.setenv("LLM_MODEL", "model")
    with pytest.raises(OrchestratorConfigurationError):
        OrchestratorConfig.from_environment()

    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:9999/llm")
    assert OrchestratorConfig.from_environment().model == "model"


def test_redirect_and_response_size_are_rejected():
    async def scenario():
        async def redirect_handler(request):
            return httpx.Response(302, headers={"location": "https://other.example"})

        client = httpx.AsyncClient(transport=httpx.MockTransport(redirect_handler))
        adapter = HttpLLMClient(client, "https://llm.example", "secret", "model")
        with pytest.raises(LLMClientError) as redirect_error:
            await adapter.generate_plan(LLMRequest("p", {}, ()))
        assert not redirect_error.value.retryable
        await client.aclose()

        async def large_handler(request):
            return httpx.Response(200, content=b"x" * 101)

        client = httpx.AsyncClient(transport=httpx.MockTransport(large_handler))
        adapter = HttpLLMClient(client, "https://llm.example", "secret", "model", max_response_bytes=100)
        with pytest.raises(LLMResponseTooLargeError):
            await adapter.generate_plan(LLMRequest("p", {}, ()))
        await client.aclose()

    asyncio.run(scenario())


def test_llm_client_uses_120_second_timeout():
    async def scenario():
        client = httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"content": "[]"})))
        adapter = HttpLLMClient(client, "https://llm.example", "secret", "model")
        assert adapter._timeout.connect == 120.0
        assert await adapter.generate_plan(LLMRequest("p", {}, ())) == "[]"
        await client.aclose()

    asyncio.run(scenario())


def test_action_failure_preserves_partial_workspace(db_session, test_storage):
    job = JobService(db_session, test_storage).create_job("failure prompt")
    client = FakeLLMClient([
        '[{"action":"WRITE_FILE","path":"partial.txt","content":"keep"},'
        '{"action":"CREATE_ARTIFACT","path":"missing.stl"}]'
    ])
    service = JobOrchestratorService(
        OrchestratorRepository(TestingSessionLocal), TestingSessionLocal, test_storage,
        client, ActionPlanParser(), SecurityPolicyValidator(test_storage.base_dir),
        ActionExecutor(test_storage, FakeRunner(), TestingSessionLocal), OrchestrationConcurrencyGate(),
    )
    assert not asyncio.run(service.run(job.id))
    assert test_storage.read_file(job.id, "partial.txt") == b"keep"
    db_session.expire_all()
    assert db_session.get(Job, job.id).status == "FAILED"


def test_stale_running_jobs_recovered_at_startup(db_session):
    stale = Job(
        id=uuid7(), prompt="stale", status="RUNNING",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=16),
    )
    recent = Job(
        id=uuid7(), prompt="recent", status="RUNNING",
        updated_at=datetime.now(timezone.utc) - timedelta(minutes=5),
    )
    db_session.add_all([stale, recent])
    db_session.commit()

    recovered = StaleJobRecoveryService(OrchestratorRepository(TestingSessionLocal)).recover()
    db_session.expire_all()
    assert recovered == 1
    assert db_session.get(Job, stale.id).status == "FAILED"
    assert db_session.get(Job, recent.id).status == "RUNNING"
    assert db_session.query(EventLog).filter(EventLog.job_id == stale.id).count() == 1


def test_llm_client_openai_format():
    import json
    async def scenario():
        called_with_payload = None
        async def mock_handler(request):
            nonlocal called_with_payload
            called_with_payload = json.loads(request.read())
            return httpx.Response(200, json={"choices": [{"message": {"content": "[]"}}]})
            
        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = HttpLLMClient(client, "https://api.openai.com/v1/chat/completions", "secret", "model")
        res = await adapter.generate_plan(LLMRequest("p", {"a.txt": "aa"}, ("WRITE_FILE",)))
        assert res == "[]"
        assert "messages" in called_with_payload
        assert called_with_payload["model"] == "model"
        assert called_with_payload["messages"][0]["role"] == "system"
        assert called_with_payload["messages"][1]["role"] == "user"
        assert "[a.txt]" in called_with_payload["messages"][1]["content"]
        await client.aclose()

    asyncio.run(scenario())


def test_llm_client_system_prompt_contains_schema():
    """R-10: 시스템 프롬프트에 RUN_TOOL의 정확한 필드명(tool_name, args)이 포함되어야 함."""
    import json

    async def scenario():
        captured_payload = None

        async def mock_handler(request):
            nonlocal captured_payload
            captured_payload = json.loads(request.read())
            return httpx.Response(200, json={"choices": [{"message": {"content": "[]"}}]})

        client = httpx.AsyncClient(transport=httpx.MockTransport(mock_handler))
        adapter = HttpLLMClient(
            client,
            "https://api.openai.com/v1/chat/completions",
            "secret",
            "model",
        )
        await adapter.generate_plan(
            LLMRequest("build a dice", {}, ("CREATE_DIRECTORY", "WRITE_FILE", "RUN_TOOL", "CREATE_ARTIFACT"))
        )
        await client.aclose()

        system_content = captured_payload["messages"][0]["content"]
        # tool_name 과 args 필드명이 시스템 프롬프트에 명시되어 있어야 함
        assert "tool_name" in system_content, "시스템 프롬프트에 'tool_name' 필드명이 포함되어야 합니다"
        assert '"args"' in system_content, "시스템 프롬프트에 'args' 필드명이 포함되어야 합니다"
        assert "openscad" in system_content, "시스템 프롬프트에 허용 도구명 'openscad'가 명시되어야 합니다"
        # 잘못된 필드명이 예시로 포함되어선 안 됨 (필드명 지시문만 포함)
        assert '"tool":' not in system_content, "시스템 프롬프트에 잘못된 필드명 'tool'이 포함되어선 안 됩니다"
        assert '"inputs":' not in system_content, "시스템 프롬프트에 잘못된 필드명 'inputs'가 포함되어선 안 됩니다"

    asyncio.run(scenario())


def test_orchestration_failed_log_includes_exception_detail(caplog, db_session, test_storage):
    """R-10: ORCHESTRATION_FAILED 이벤트 메시지에 예외 상세 내용이 포함되어야 함."""
    job = JobService(db_session, test_storage).create_job("fail prompt")

    # LLM이 tool_name 대신 tool 필드를 반환하도록 잘못된 응답 주입
    bad_response = '[{"action": "RUN_TOOL", "tool": "openscad", "inputs": {}}]'
    llm_client = FakeLLMClient([bad_response, bad_response, bad_response])


    service = JobOrchestratorService(
        OrchestratorRepository(TestingSessionLocal),
        TestingSessionLocal,
        test_storage,
        llm_client,
        ActionPlanParser(),
        SecurityPolicyValidator(test_storage.base_dir),
        ActionExecutor(test_storage, FakeRunner(), TestingSessionLocal),
        OrchestrationConcurrencyGate(),
    )

    with caplog.at_level(logging.ERROR, logger="orchestrator.service"):
        result = asyncio.run(service.run(job.id))
    assert result is False

    server_log = next(
        record
        for record in caplog.records
        if "Orchestration failed for job_id=" in record.getMessage()
    )
    assert str(job.id) in server_log.getMessage()
    assert "LLMPlanValidationError" in server_log.getMessage()
    assert server_log.exc_info is not None

    db_session.expire_all()
    failed_job = db_session.get(Job, job.id)
    assert failed_job.status == "FAILED"

    # ORCHESTRATION_FAILED 이벤트 로그에 상세 메시지 포함 여부 확인
    # OrchestratorRepository.transition()은 event_type="SYSTEM_EVENT"로 저장하고
    # 메시지는 "[ORCHESTRATION_FAILED] Orchestration failed: ..." 형식으로 저장됨
    failed_log = (
        db_session.query(EventLog)
        .filter(
            EventLog.job_id == job.id,
            EventLog.event_type == "SYSTEM_EVENT",
            EventLog.message.contains("ORCHESTRATION_FAILED"),
        )
        .first()
    )
    assert failed_log is not None
    assert "LLMPlanValidationError" in failed_log.message
    assert "Detail:" in failed_log.message, "에러 상세 메시지(Detail:)가 이벤트 로그에 포함되어야 합니다"
    # 상세 메시지에 Pydantic 검증 오류 내용이 포함됨을 확인
    assert "tool_name" in failed_log.message or "validation" in failed_log.message.lower()


def test_orchestration_transition_failure_is_logged(caplog, db_session, test_storage):
    """R-13: EventLog transition failure must not hide the original traceback."""
    job = JobService(db_session, test_storage).create_job("sensitive prompt")

    class FailingTransitionRepository(OrchestratorRepository):
        def transition(
            self,
            job_id,
            expected_statuses,
            target_status,
            event_code,
            message,
        ):
            if event_code == "ORCHESTRATION_FAILED":
                raise RuntimeError("event store unavailable")
            return super().transition(
                job_id,
                expected_statuses,
                target_status,
                event_code,
                message,
            )

    service = JobOrchestratorService(
        FailingTransitionRepository(TestingSessionLocal),
        TestingSessionLocal,
        test_storage,
        FakeLLMClient(['[{"action": "RUN_TOOL", "tool": "openscad"}]']),
        ActionPlanParser(),
        SecurityPolicyValidator(test_storage.base_dir),
        ActionExecutor(test_storage, FakeRunner(), TestingSessionLocal),
        OrchestrationConcurrencyGate(),
    )

    with caplog.at_level(logging.ERROR, logger="orchestrator.service"):
        assert asyncio.run(service.run(job.id)) is False

    messages = [record.getMessage() for record in caplog.records]
    assert any("Orchestration failed for job_id=" in message for message in messages)
    assert any("Failed to persist orchestration failure" in message for message in messages)
    assert all("sensitive prompt" not in message for message in messages)
    assert sum(record.exc_info is not None for record in caplog.records) >= 2


def test_orchestrator_refines_when_scad_static_validation_fails(db_session, test_storage):
    import json
    # R-15: SCAD 검증 에러 발생 시 refinement loop 재시도 동작 검증
    job = JobService(db_session, test_storage).create_job("create scad cube")

    bad_scad_content = "cube([10, 20, 30]);\nvector = [1, 2, 3];\necho(vector.x);"
    bad_plan = f'[{{"action":"WRITE_FILE","path":"model.scad","content":{json.dumps(bad_scad_content)}}}]'

    good_scad_content = "cube([10, 20, 30]);"
    good_plan = f'[{{"action":"WRITE_FILE","path":"model.scad","content":{json.dumps(good_scad_content)}}}]'

    llm_client = FakeLLMClient([bad_plan, good_plan])

    repository = OrchestratorRepository(TestingSessionLocal)
    service = JobOrchestratorService(
        repository,
        TestingSessionLocal,
        test_storage,
        llm_client,
        ActionPlanParser(),
        SecurityPolicyValidator(test_storage.base_dir),
        ActionExecutor(test_storage, FakeRunner(), TestingSessionLocal),
        OrchestrationConcurrencyGate(),
    )

    success = asyncio.run(service.run(job.id))
    assert success is True

    assert len(llm_client.requests) == 2
    assert llm_client.requests[1].retry_feedback is not None
    assert "[SCAD_VECTOR_PROPERTY_ACCESS]" in llm_client.requests[1].retry_feedback

    db_session.expire_all()
    completed_job = db_session.get(Job, job.id)
    assert completed_job.status == "COMPLETED"
    assert test_storage.read_file(job.id, "model.scad").decode("utf-8") == good_scad_content

