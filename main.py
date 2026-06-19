import logging
import httpx
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from database import engine, Base, SessionLocal
from limiter import limiter
from jobs.router import router as jobs_router
from sse.router import router as sse_router
from llm.client import HttpLLMClient
from llm.parser import ActionPlanParser
from llm.validator import SecurityPolicyValidator
from orchestrator.actions import ActionExecutor
from orchestrator.concurrency import OrchestrationConcurrencyGate
from orchestrator.config import OrchestratorConfig
from orchestrator.recovery import StaleJobRecoveryService
from orchestrator.repository import OrchestratorRepository
from orchestrator.service import JobOrchestratorService
from runner.service import CLIExecutionRunner
from storage.local import LocalStorageService

# 기본 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# FastAPI Lifespan 이벤트 핸들러 (Startup & Shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Application starting up...")
    # app.state에 db_engine이 테스트 등에 의해 오버라이드되어 있으면 그것을 사용하고,
    # 없으면 database.py에 정의된 기본 engine을 사용합니다.
    db_engine = getattr(app.state, "db_engine", engine)
    Base.metadata.create_all(bind=db_engine)
    session_factory = getattr(app.state, "session_factory", SessionLocal)
    storage = getattr(app.state, "storage_service", LocalStorageService())
    config = OrchestratorConfig.from_environment()
    http_client = httpx.AsyncClient(follow_redirects=False)
    repository = OrchestratorRepository(session_factory)
    StaleJobRecoveryService(repository).recover()
    llm_client = HttpLLMClient(http_client, config.endpoint, config.api_key, config.model)
    action_executor = ActionExecutor(storage, CLIExecutionRunner(), session_factory)
    app.state.orchestrator_service = JobOrchestratorService(
        repository,
        session_factory,
        storage,
        llm_client,
        ActionPlanParser(),
        SecurityPolicyValidator(getattr(storage, "base_dir", None)),
        action_executor,
        OrchestrationConcurrencyGate(),
    )
    yield
    await http_client.aclose()
    logger.info("Application shutting down...")
    # 필요한 경우 자원 해제 코드를 여기에 작성합니다.

# FastAPI 애플리케이션 생성
app = FastAPI(
    title="Workspace CLI Execution Platform API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS 미들웨어 설정 (S3에 배포될 프론트엔드가 접속할 수 있도록 허용)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 실운영 환경에서는 구체적인 도메인 지정을 권장합니다.
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# SlowAPI 속도 제한기 설정 및 미들웨어 추가
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)


# -------------------------------------------------------------------
# 전역 예외 처리기 (Global Exception Handlers)
# -------------------------------------------------------------------

@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    """
    속도 제한 초과 시 발생하는 예외를 표준 REST API 에러 포맷으로 가공합니다.
    """
    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "detail": {
                "status": "error",
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {exc.detail}"
            }
        }
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Pydantic 필드 검증 에러를 표준 REST API 에러 포맷으로 가공합니다.
    """
    errors = exc.errors()
    first_error = errors[0] if errors else {}
    loc_str = ".".join(str(loc) for loc in first_error.get("loc", []))
    msg = f"Field '{loc_str}' : {first_error.get('msg', 'invalid value')}"
    
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "detail": {
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": msg
            }
        }
    )

@app.exception_handler(PermissionError)
async def permission_exception_handler(request: Request, exc: PermissionError):
    """
    Directory Traversal 방어 및 권한 위반 발생 시 표준 REST API 에러 포맷으로 가공합니다.
    """
    return JSONResponse(
        status_code=status.HTTP_403_FORBIDDEN,
        content={
            "detail": {
                "status": "error",
                "code": "FORBIDDEN_ACCESS",
                "message": "Access denied. Path traversal detected."
            }
        }
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """
    FastAPI/Starlette 기본 HTTPException 발생 시 표준 REST API 에러 포맷으로 가공합니다.
    """
    # 이미 표준 포맷에 부합하는 dictionary 형태인 경우 그대로 반환
    if isinstance(exc.detail, dict) and "status" in exc.detail:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail}
        )
    
    # 그 외 기본 HTTPException 문자열 세팅
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": {
                "status": "error",
                "code": "HTTP_EXCEPTION",
                "message": str(exc.detail)
            }
        }
    )

# -------------------------------------------------------------------
# 라우터 등록
# -------------------------------------------------------------------
app.include_router(jobs_router)
app.include_router(sse_router)

@app.get("/")
def read_root():
    return {"message": "Workspace CLI Execution Platform Backend API is running."}
