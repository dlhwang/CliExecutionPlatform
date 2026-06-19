import asyncio
import statistics
import time
from datetime import datetime, timezone
from uuid import UUID

import pytest
from fastapi import status
from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from uuid6 import uuid7

from database import Base
from jobs.models import EventLog, Job
from sse.connection_registry import ConnectionRegistry
from sse.repository import EventLogPollingRepository, EventRecord, PollSnapshot
from sse.security import StreamTokenConfigurationError, StreamTokenService
from sse.service import SSEStreamService

TEST_STREAM_TOKEN_SECRET = "unit-test-stream-token-secret"


def _create_job_with_events(
    db: Session,
    *,
    status_value: str = "COMPLETED",
    event_count: int = 3,
) -> tuple[Job, list[EventLog]]:
    job = Job(id=uuid7(), prompt="SSE test prompt", status=status_value)
    db.add(job)
    db.commit()

    events = [
        EventLog(
            job_id=job.id,
            event_type="CLI_OUTPUT",
            message=f"line-{index}",
        )
        for index in range(event_count)
    ]
    db.add_all(events)
    db.commit()
    for event in events:
        db.refresh(event)
    return job, events


def _token(job_id) -> str:
    return StreamTokenService(TEST_STREAM_TOKEN_SECRET).create_token(job_id)


def _stream_headers(job_id, **extra) -> dict[str, str]:
    return {"X-Stream-Token": _token(job_id), **extra}


def test_job_creation_returns_stream_access(client):
    response = client.post(
        "/api/v1/jobs",
        json={"prompt": "SSE stream access test prompt"},
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["stream_url"] == f"/api/v1/jobs/{data['id']}/stream"
    assert StreamTokenService(TEST_STREAM_TOKEN_SECRET).verify_token(
        UUID(data["id"]), data["stream_token"]
    )


def test_sse_streaming_completed_job(client, db_session):
    job, events = _create_job_with_events(db_session)

    response = client.get(
        f"/api/v1/jobs/{job.id}/stream",
        headers=_stream_headers(job.id),
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.headers["content-type"].startswith("text/event-stream")
    for event in events:
        assert f"id: {event.id}\n" in response.text
        assert "event: CLI_OUTPUT\n" in response.text
        assert f'"message":"{event.message}"' in response.text
    assert "event: STREAM_END\n" in response.text
    assert '"status":"COMPLETED"' in response.text


def test_sse_catchup_after_last_event_id(client, db_session):
    job, events = _create_job_with_events(db_session)

    response = client.get(
        f"/api/v1/jobs/{job.id}/stream",
        headers=_stream_headers(job.id, **{"Last-Event-ID": str(events[1].id)}),
    )

    assert response.status_code == status.HTTP_200_OK
    assert f"id: {events[0].id}\n" not in response.text
    assert f"id: {events[1].id}\n" not in response.text
    assert f"id: {events[2].id}\n" in response.text
    assert "event: STREAM_END\n" in response.text


@pytest.mark.parametrize("last_event_id", ["not-a-number", "999999999"])
def test_last_event_id_invalid_or_out_of_range_restarts_from_first(
    client,
    db_session,
    last_event_id,
):
    job, events = _create_job_with_events(db_session)

    response = client.get(
        f"/api/v1/jobs/{job.id}/stream",
        headers=_stream_headers(job.id, **{"Last-Event-ID": last_event_id}),
    )

    assert response.status_code == status.HTTP_200_OK
    assert f"id: {events[0].id}\n" in response.text


def test_stream_rejects_missing_job_and_invalid_token(client, db_session):
    missing_id = uuid7()
    missing_response = client.get(
        f"/api/v1/jobs/{missing_id}/stream",
        headers=_stream_headers(missing_id),
    )
    assert missing_response.status_code == status.HTTP_404_NOT_FOUND

    job, _ = _create_job_with_events(db_session)
    forbidden_response = client.get(
        f"/api/v1/jobs/{job.id}/stream",
        headers={"X-Stream-Token": "v1.invalid"},
    )
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden_response.json()["detail"]["code"] == "INVALID_STREAM_TOKEN"


def test_stream_token_is_job_scoped():
    service = StreamTokenService(TEST_STREAM_TOKEN_SECRET)
    first_job = uuid7()
    second_job = uuid7()
    token = service.create_token(first_job)

    assert service.verify_token(first_job, token)
    assert not service.verify_token(second_job, token)
    assert not service.verify_token(first_job, None)


def test_missing_secret_is_rejected(monkeypatch):
    monkeypatch.delenv("SSE_STREAM_TOKEN_SECRET", raising=False)
    with pytest.raises(StreamTokenConfigurationError):
        StreamTokenService.from_environment()


def test_connection_registry_rejects_twenty_first_connection():
    async def scenario():
        registry = ConnectionRegistry(max_connections=20)
        results = [await registry.try_acquire() for _ in range(21)]
        assert results == ([True] * 20) + [False]
        for _ in range(20):
            await registry.release()
        assert await registry.active_count() == 0

    asyncio.run(scenario())


def test_stream_endpoint_returns_503_at_connection_capacity(
    client,
    db_session,
    sse_registry,
):
    job, _ = _create_job_with_events(db_session)

    async def fill_registry():
        for _ in range(20):
            assert await sse_registry.try_acquire()

    asyncio.run(fill_registry())
    response = client.get(
        f"/api/v1/jobs/{job.id}/stream",
        headers=_stream_headers(job.id),
    )

    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert response.json()["detail"]["code"] == "STREAM_CAPACITY_EXCEEDED"


def test_repository_uses_cursor_order_and_batch_limit(db_session):
    job, events = _create_job_with_events(db_session, event_count=105)
    session_factory = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=db_session.get_bind(),
    )
    repository = EventLogPollingRepository(session_factory)

    first_page = repository.fetch_snapshot(job.id, 0)
    second_page = repository.fetch_snapshot(job.id, first_page.events[-1].event_id)

    assert len(first_page.events) == 100
    assert len(second_page.events) == 5
    assert [event.event_id for event in first_page.events] == sorted(
        event.id for event in events[:100]
    )


class _SequenceRepository:
    def __init__(self, snapshots=None, failures=0, failure=None):
        self.snapshots = list(snapshots or [])
        self.failures = failures
        self.failure = failure
        self.calls = 0

    def fetch_snapshot(self, job_id, last_seen_id, limit):
        self.calls += 1
        if self.calls <= self.failures:
            raise self.failure
        if self.snapshots:
            return self.snapshots.pop(0)
        return PollSnapshot(events=(), job_status="COMPLETED")


async def _direct_run_sync(function, *args, **kwargs):
    return function(*args, **kwargs)


async def _consume(service, job_id, cursor=0):
    return [frame async for frame in service.stream(job_id, cursor)]


def test_stream_emits_reconnect_at_max_duration():
    async def scenario():
        registry = ConnectionRegistry()
        assert await registry.try_acquire()
        clock_values = iter((0.0, 601.0))
        service = SSEStreamService(
            _SequenceRepository(),
            registry,
            clock=lambda: next(clock_values),
            run_sync=_direct_run_sync,
        )
        frames = await _consume(service, uuid7())
        assert "event: STREAM_RECONNECT\n" in frames[0]
        assert await registry.active_count() == 0

    asyncio.run(scenario())


def test_transient_db_error_retries_three_times():
    async def scenario():
        delays = []

        async def record_sleep(delay):
            delays.append(delay)

        failure = OperationalError("SELECT", {}, Exception("temporary"))
        repository = _SequenceRepository(failures=3, failure=failure)
        registry = ConnectionRegistry()
        assert await registry.try_acquire()
        service = SSEStreamService(
            repository,
            registry,
            sleep=record_sleep,
            run_sync=_direct_run_sync,
        )

        frames = await _consume(service, uuid7())

        assert repository.calls == 4
        assert delays == [0.5, 1.0, 2.0]
        assert "event: STREAM_END\n" in frames[-1]
        assert await registry.active_count() == 0

    asyncio.run(scenario())


def test_connection_slot_released_on_error():
    async def scenario():
        repository = _SequenceRepository(failures=1, failure=ValueError("broken"))
        registry = ConnectionRegistry()
        assert await registry.try_acquire()
        service = SSEStreamService(
            repository,
            registry,
            run_sync=_direct_run_sync,
        )

        frames = await _consume(service, uuid7())

        assert "event: STREAM_ERROR\n" in frames[-1]
        assert await registry.active_count() == 0

    asyncio.run(scenario())


def test_running_job_terminal_drain():
    async def scenario():
        job_id = uuid7()
        first_event = EventRecord(
            event_id=1,
            job_id=job_id,
            event_type="CLI_OUTPUT",
            message="running",
            created_at=datetime.now(timezone.utc),
        )
        final_event = EventRecord(
            event_id=2,
            job_id=job_id,
            event_type="SYSTEM_EVENT",
            message="done",
            created_at=datetime.now(timezone.utc),
        )
        repository = _SequenceRepository(
            snapshots=[
                PollSnapshot(events=(first_event,), job_status="RUNNING"),
                PollSnapshot(events=(final_event,), job_status="COMPLETED"),
            ]
        )
        registry = ConnectionRegistry()
        assert await registry.try_acquire()

        async def no_sleep(delay):
            return None

        service = SSEStreamService(
            repository,
            registry,
            sleep=no_sleep,
            run_sync=_direct_run_sync,
        )
        frames = await _consume(service, job_id)

        assert "id: 1\n" in frames[0]
        assert "id: 2\n" in frames[1]
        assert "event: STREAM_END\n" in frames[2]

    asyncio.run(scenario())


def test_twenty_streams_average_delivery_under_three_seconds(tmp_path):
    performance_engine = create_engine(
        f"sqlite:///{tmp_path / 'sse-performance.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(bind=performance_engine)
    performance_sessions = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=performance_engine,
    )
    seed_session = performance_sessions()
    jobs = []
    try:
        for index in range(20):
            job = Job(id=uuid7(), prompt=f"performance-{index}", status="COMPLETED")
            seed_session.add(job)
            seed_session.flush()
            seed_session.add(
                EventLog(
                    job_id=job.id,
                    event_type="CLI_OUTPUT",
                    message="ready",
                )
            )
            jobs.append(job.id)
        seed_session.commit()
    finally:
        seed_session.close()

    async def scenario():
        registry = ConnectionRegistry(max_connections=20)
        latencies = []

        async def run_stream(job_id):
            repository = EventLogPollingRepository(performance_sessions)
            assert await registry.try_acquire()
            service = SSEStreamService(repository, registry)
            started = time.perf_counter()
            frames = await _consume(service, job_id)
            latencies.append(time.perf_counter() - started)
            assert "event: CLI_OUTPUT\n" in frames[0]

        await asyncio.gather(*(run_stream(job_id) for job_id in jobs))
        assert statistics.mean(latencies) < 3.0
        assert await registry.active_count() == 0

    try:
        asyncio.run(scenario())
    finally:
        performance_engine.dispose()
