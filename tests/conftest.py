import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import app
from jobs.router import get_storage_service
from jobs.router import get_orchestrator_service
from limiter import limiter
from sse.connection_registry import ConnectionRegistry
from sse.router import get_connection_registry, get_sse_session_factory
from storage.local import LocalStorageService

# SQLite 인메모리 테스트 데이터베이스 설정
# StaticPool을 사용하여 단일 커넥션을 유지해 테이블 정의가 세션 도중 유실되지 않도록 함
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

TEST_STREAM_TOKEN_SECRET = "unit-test-stream-token-secret"


@pytest.fixture(autouse=True)
def isolated_process_state(monkeypatch):
    monkeypatch.setenv("SSE_STREAM_TOKEN_SECRET", TEST_STREAM_TOKEN_SECRET)
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("LLM_ENDPOINT", "http://localhost:9999/llm")
    monkeypatch.setenv("LLM_API_KEY", "test-llm-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    limiter._storage.reset()
    yield
    limiter._storage.reset()


@pytest.fixture(name="sse_registry")
def sse_registry_fixture():
    return ConnectionRegistry()

@pytest.fixture(name="db_session")
def db_session_fixture():
    """
    각 테스트별로 격리된 데이터베이스 세션을 제공하며,
    테스트 시작 시 테이블을 생성하고 종료 시 드롭합니다.
    """
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)

@pytest.fixture(name="test_storage")
def test_storage_fixture(tmp_path):
    """
    각 테스트별로 격리된 임시 로컬 파일시스템 작업 공간(Workspace)을 구성합니다.
    pytest의 내장 tmp_path 피처를 사용하여 테스트 종료 시 자동 청소됩니다.
    """
    storage_dir = tmp_path / ".workspaces"
    storage = LocalStorageService(base_dir=storage_dir)
    return storage

@pytest.fixture(name="client")
def client_fixture(db_session, test_storage, sse_registry):
    """
    FastAPI TestClient 피처로, DB 세션 및 Storage Service 의존성을 오버라이드하여 제공합니다.
    """
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    def override_get_storage_service():
        return test_storage

    def override_get_sse_session_factory():
        return TestingSessionLocal

    def override_get_connection_registry():
        return sse_registry

    class NoOpOrchestrator:
        async def run(self, job_id):
            return True

    def override_get_orchestrator_service():
        return NoOpOrchestrator()

    # lifespan startup 시 PostgreSQL 대신 SQLite 테스트 엔진을 바라보도록 설정
    app.state.db_engine = engine
    app.state.session_factory = TestingSessionLocal
    app.state.storage_service = test_storage
    
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_storage_service] = override_get_storage_service
    app.dependency_overrides[get_sse_session_factory] = override_get_sse_session_factory
    app.dependency_overrides[get_connection_registry] = override_get_connection_registry
    app.dependency_overrides[get_orchestrator_service] = override_get_orchestrator_service
    
    with TestClient(app) as c:
        yield c
        
    app.dependency_overrides.clear()
    if hasattr(app.state, "db_engine"):
        del app.state.db_engine
    for attribute in ("session_factory", "storage_service", "orchestrator_service"):
        if hasattr(app.state, attribute):
            delattr(app.state, attribute)
