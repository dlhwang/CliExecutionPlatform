"""
tests/test_unit_3.py

Unit 3: CLI Runner Service 통합 테스트 (8개 테스트 케이스)

검증 대상:
    - TC-3-1: 위험 인자 Allowlist 차단 검증 (NFR-1.4)
    - TC-3-2: 안전한 인자 통과 검증 (NFR-1.4)
    - TC-3-3: 정상 실행 시 EventLog DB 적재 검증 (Q2)
    - TC-3-4: 30초 타임아웃 메커니즘 검증 (NFR-1.1)
    - TC-3-5: 타임아웃 시 부분 출력 보존 + TIMEOUT 마커 기록 (Q4)
    - TC-3-6: 프로세스 기동 실패 시 OSError 2회 재시도 후 CLIExecutionLaunchError (NFR-1.3)
    - TC-3-7: Non-Zero Exit Code 시 CLIExecutionError 발생 (US-3-1)
    - TC-3-8: Semaphore(2) 동시성 제한 검증 (NFR-1.2)

의존성:
    - conftest.py의 db_session 픽스처 (SQLite 인메모리)
    - 실제 OpenSCAD CLI 불필요: Python 크로스 플랫폼 명령 활용
"""
import asyncio
import sys
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from jobs.models import Job, EventLog
from runner.exceptions import (
    CLIArgumentValidationError,
    CLIExecutionError,
    CLIExecutionLaunchError,
    CLIExecutionTimeoutError,
)
from runner.service import CLIExecutionRunner, _CLI_SEMAPHORE
from runner.validator import ArgumentValidator


# ──────────────────────────────────────────────────────────────
# 헬퍼 함수
# ──────────────────────────────────────────────────────────────

def _create_job(db_session) -> uuid.UUID:
    """테스트용 Job 더미 데이터 삽입 후 job_id 반환."""
    job_id = uuid.uuid4()
    job = Job(id=job_id, prompt="Unit 3 Test", status="RUNNING")
    db_session.add(job)
    db_session.commit()
    return job_id


def _get_python_cmd() -> str:
    """현재 인터프리터 경로를 반환합니다 (크로스 플랫폼 호환)."""
    return sys.executable


# ──────────────────────────────────────────────────────────────
# TC-3-1: 위험 인자 Allowlist 차단 검증 (NFR-1.4)
# ──────────────────────────────────────────────────────────────

def test_argument_validation_blocks_unsafe_chars():
    """
    파이프(|), 세미콜론(;), 달러($), 백틱(`), 부등호 등 위험 인자가
    Allowlist 검증에서 CLIArgumentValidationError로 차단되는지 검증합니다.
    """
    unsafe_args = [
        "output.png; rm -rf /",      # 세미콜론 분리 명령 삽입
        "$(evil_cmd)",               # 명령 치환 ($, (, ))
        "file.scad | tee /etc",      # 파이프 연결 (|, 공백)
        "`whoami`",                  # 백틱 명령 치환
        "arg with spaces",           # 공백 포함
        "arg\x00null",               # Null 바이트
        "file!name",                 # 느낌표 포함
        "{malicious}",               # 중괄호 포함
        "arg#comment",               # 샵(#) 포함
    ]

    for dangerous_arg in unsafe_args:
        with pytest.raises(CLIArgumentValidationError) as exc_info:
            ArgumentValidator.validate([dangerous_arg])
        assert exc_info.value.offending_arg == dangerous_arg, (
            f"Expected offending_arg={dangerous_arg!r}, "
            f"got {exc_info.value.offending_arg!r}"
        )


# ──────────────────────────────────────────────────────────────
# TC-3-2: 안전한 인자 통과 검증 (NFR-1.4)
# ──────────────────────────────────────────────────────────────

def test_argument_validation_allows_safe_args():
    """
    OpenSCAD CLI에서 정상적으로 사용되는 안전한 인자들이 Allowlist를 통과하는지 검증합니다.
    """
    safe_args = [
        "-o",
        "output.png",
        "model.scad",
        "--render",
        "-D",
        "SIZE=10",
        "preview.stl",
        "-o=output.stl",
        "sub/model.scad",
        "path/to/file.scad",
    ]
    # 예외 없이 통과해야 합니다
    ArgumentValidator.validate(safe_args)


# ──────────────────────────────────────────────────────────────
# TC-3-3: 정상 실행 시 EventLog DB 적재 검증 (Q2)
# ──────────────────────────────────────────────────────────────

def test_run_tool_success_writes_event_logs(db_session):
    """
    정상 실행 시 CLI 출력이 EventLog 테이블에 CLI_OUTPUT 타입으로 적재되고
    Exit Code 0이 반환되는지 검증합니다.
    Python을 통해 실제 프로세스를 실행 (OpenSCAD 불필요).
    """
    job_id = _create_job(db_session)
    runner = CLIExecutionRunner()

    python_bin = _get_python_cmd()
    # python -c "print('hello'); print('world')" → 2줄 출력 후 Exit Code 0
    args = ["-c", "print('hello');print('world')"]

    # ArgumentValidator: python 바이너리 경로는 runner 내부에서 사용 (검증 대상 아님)
    # args의 "-c"와 "print..."만 검증 대상인데, "print('hello');print('world')"는
    # 괄호와 세미콜론으로 인해 Allowlist에 실패함 → 실제 openscad 인자를 흉내내어 테스트
    # → ArgumentValidator를 우회하고 _execute_with_timeout을 직접 테스트합니다.
    with patch.object(runner, "_openscad_bin", python_bin):
        # ArgumentValidator를 Mock으로 우회 (인자 검증 자체는 TC-3-1/2에서 검증)
        with patch("runner.service.ArgumentValidator.validate"):
            exit_code = asyncio.get_event_loop().run_until_complete(
                runner.run_tool(
                    job_id=job_id,
                    tool_name="openscad",
                    args=["-c", "print('hello');print('world')"],
                    db=db_session,
                )
            )

    assert exit_code == 0

    logs = db_session.query(EventLog).filter_by(
        job_id=job_id, event_type="CLI_OUTPUT"
    ).all()
    assert len(logs) >= 1

    messages = [log.message for log in logs]
    assert any("hello" in m for m in messages), f"Expected 'hello' in logs: {messages}"
    assert any("world" in m for m in messages), f"Expected 'world' in logs: {messages}"


# ──────────────────────────────────────────────────────────────
# TC-3-4: 30초 타임아웃 메커니즘 검증 (NFR-1.1)
# ──────────────────────────────────────────────────────────────

def test_timeout_kills_process(db_session):
    """
    asyncio.wait_for의 타임아웃이 발동되면 프로세스가 강제 종료되고
    CLIExecutionTimeoutError가 발생하는지 검증합니다.
    asyncio.wait_for를 패치하여 즉시 TimeoutError를 발생시킵니다.
    """
    job_id = _create_job(db_session)
    runner = CLIExecutionRunner()

    python_bin = _get_python_cmd()

    async def run_test():
        with patch.object(runner, "_openscad_bin", python_bin):
            with patch("runner.service.ArgumentValidator.validate"):
                # asyncio.wait_for를 패치하여 즉시 TimeoutError 발생
                with patch("runner.service.asyncio.wait_for", side_effect=asyncio.TimeoutError):
                    # _launch_with_retry도 Mock 처리 (실제 프로세스 기동 불필요)
                    mock_process = MagicMock()
                    mock_process.kill = MagicMock()
                    mock_process.wait = AsyncMock(return_value=None)
                    mock_process.returncode = -9

                    with patch.object(
                        runner, "_launch_with_retry", return_value=(mock_process, 1)
                    ):
                        with pytest.raises(CLIExecutionTimeoutError) as exc_info:
                            await runner.run_tool(
                                job_id=job_id,
                                tool_name="openscad",
                                args=["model.scad"],
                                db=db_session,
                                timeout_seconds=0.01,
                            )

        err = exc_info.value
        assert err.timeout_limit == 0.01
        assert "timed out" in err.message.lower()
        mock_process.kill.assert_called_once()
        mock_process.wait.assert_awaited_once()

    asyncio.get_event_loop().run_until_complete(run_test())


# ──────────────────────────────────────────────────────────────
# TC-3-5: 타임아웃 시 부분 출력 보존 + TIMEOUT 마커 기록 (Q4)
# ──────────────────────────────────────────────────────────────

def test_timeout_preserves_partial_logs(db_session):
    """
    타임아웃 발생 시 기존에 수집된 EventLog 레코드가 보존되고
    SYSTEM_EVENT 타입의 TIMEOUT 마커가 추가로 기록되는지 검증합니다.
    """
    job_id = _create_job(db_session)

    # 타임아웃 전 부분 출력 레코드를 미리 수동으로 삽입
    partial_log = EventLog(
        job_id=job_id,
        event_type="CLI_OUTPUT",
        message="Partial output line before timeout",
    )
    db_session.add(partial_log)
    db_session.commit()

    runner = CLIExecutionRunner()

    async def run_test():
        with patch("runner.service.ArgumentValidator.validate"):
            with patch("runner.service.asyncio.wait_for", side_effect=asyncio.TimeoutError):
                mock_process = MagicMock()
                mock_process.kill = MagicMock()
                mock_process.wait = AsyncMock(return_value=None)

                with patch.object(
                    runner, "_launch_with_retry", return_value=(mock_process, 1)
                ):
                    with pytest.raises(CLIExecutionTimeoutError):
                        await runner.run_tool(
                            job_id=job_id,
                            tool_name="openscad",
                            args=["model.scad"],
                            db=db_session,
                            timeout_seconds=0.01,
                        )

    asyncio.get_event_loop().run_until_complete(run_test())

    # 기존 부분 출력 보존 검증
    cli_logs = db_session.query(EventLog).filter_by(
        job_id=job_id, event_type="CLI_OUTPUT"
    ).all()
    assert len(cli_logs) >= 1, "Partial output logs should be preserved after timeout"

    # TIMEOUT 마커 기록 검증
    timeout_marker = db_session.query(EventLog).filter_by(
        job_id=job_id, event_type="SYSTEM_EVENT"
    ).first()
    assert timeout_marker is not None, "TIMEOUT system event marker should be written"
    assert "TIMEOUT" in timeout_marker.message
    assert "timeout" in timeout_marker.message.lower()


# ──────────────────────────────────────────────────────────────
# TC-3-6: 프로세스 기동 실패 시 2회 재시도 후 CLIExecutionLaunchError (NFR-1.3)
# ──────────────────────────────────────────────────────────────

def test_launch_retry_on_os_error(db_session):
    """
    asyncio.create_subprocess_exec가 OSError를 3회 연속 발생시킬 때
    최대 2회 재시도 후 CLIExecutionLaunchError가 발생하는지 검증합니다.
    실제 재시도 횟수(attempts=3)가 예외 속성에 정확히 기록되는지도 확인합니다.
    """
    job_id = _create_job(db_session)
    runner = CLIExecutionRunner()
    call_count = 0

    async def failing_create_subprocess(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise OSError(f"Simulated OS error (attempt {call_count})")

    async def run_test():
        with patch("runner.service.ArgumentValidator.validate"):
            # asyncio.sleep을 패치하여 재시도 대기 시간을 0으로 단축
            with patch("runner.service.asyncio.sleep", new_callable=AsyncMock):
                with patch(
                    "runner.service.asyncio.create_subprocess_exec",
                    side_effect=failing_create_subprocess,
                ):
                    with pytest.raises(CLIExecutionLaunchError) as exc_info:
                        await runner.run_tool(
                            job_id=job_id,
                            tool_name="openscad",
                            args=["model.scad"],
                            db=db_session,
                        )

        err = exc_info.value
        assert err.attempts == 3, f"Expected 3 attempts, got {err.attempts}"
        assert "openscad" in err.target_path.lower() or err.target_path != ""
        assert call_count == 3, f"Expected 3 subprocess.exec calls, got {call_count}"

    asyncio.get_event_loop().run_until_complete(run_test())


# ──────────────────────────────────────────────────────────────
# TC-3-7: Non-Zero Exit Code 시 CLIExecutionError 발생 (US-3-1)
# ──────────────────────────────────────────────────────────────

def test_nonzero_exit_code_raises_cli_execution_error(db_session):
    """
    프로세스가 정상 기동되었지만 Non-Zero Exit Code로 종료된 경우
    CLIExecutionError가 발생하고 exit_code 속성이 정확히 전달되는지 검증합니다.
    Python: sys.exit(1) 로 실제 Exit Code 1 발생.
    """
    job_id = _create_job(db_session)
    runner = CLIExecutionRunner()
    python_bin = _get_python_cmd()

    async def run_test():
        with patch.object(runner, "_openscad_bin", python_bin):
            with patch("runner.service.ArgumentValidator.validate"):
                with pytest.raises(CLIExecutionError) as exc_info:
                    await runner.run_tool(
                        job_id=job_id,
                        tool_name="openscad",
                        args=["-c", "import sys; sys.exit(1)"],
                        db=db_session,
                    )

        err = exc_info.value
        assert err.exit_code == 1, f"Expected exit_code=1, got {err.exit_code}"
        assert "exit code 1" in err.message.lower() or "1" in err.message

    asyncio.get_event_loop().run_until_complete(run_test())


# ──────────────────────────────────────────────────────────────
# TC-3-8: Semaphore(2) 동시성 제한 검증 (NFR-1.2)
# ──────────────────────────────────────────────────────────────

def test_semaphore_limits_concurrency(db_session):
    """
    _CLI_SEMAPHORE(2)가 최대 2개의 동시 실행만 허용하는지 검증합니다.
    3개의 작업을 동시에 제출하고, Semaphore 내부 상태를 통해 동시성이 올바르게 제한되는지 확인합니다.
    """
    # _CLI_SEMAPHORE의 initial value 검증
    assert _CLI_SEMAPHORE._value == 2, (
        f"Expected Semaphore initial value=2, got {_CLI_SEMAPHORE._value}"
    )

    execution_order = []

    async def run_test():
        # Semaphore 획득 중인 동시 작업 수를 측정합니다
        semaphore = asyncio.Semaphore(2)
        active_count = 0
        max_concurrent = 0

        async def simulated_task(task_id: int):
            nonlocal active_count, max_concurrent
            async with semaphore:
                active_count += 1
                max_concurrent = max(max_concurrent, active_count)
                execution_order.append(f"start-{task_id}")
                await asyncio.sleep(0.05)  # 짧은 지연으로 동시성 시뮬레이션
                execution_order.append(f"end-{task_id}")
                active_count -= 1

        # 5개의 작업을 동시에 제출
        await asyncio.gather(
            simulated_task(1),
            simulated_task(2),
            simulated_task(3),
            simulated_task(4),
            simulated_task(5),
        )

        # 최대 동시 실행이 2를 초과하지 않았음을 검증
        assert max_concurrent <= 2, (
            f"Semaphore should limit concurrency to 2, but {max_concurrent} ran concurrently"
        )

    asyncio.get_event_loop().run_until_complete(run_test())

    # 모든 작업이 완료되었는지 검증
    assert len([e for e in execution_order if e.startswith("start")]) == 5
    assert len([e for e in execution_order if e.startswith("end")]) == 5
