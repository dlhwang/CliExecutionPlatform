# 기술 스택 결정서 (Tech Stack Decisions) - Unit 1: API Core & Storage Service

본 문서는 **Unit 1: API Core & Storage Service**의 비기능 요구사항을 달성하기 위한 구체적인 라이브러리 선정, 프레임워크 설정값, 그리고 데이터베이스 커넥션 풀 매개변수를 정의합니다.

---

## 1. 프레임워크 및 라이브러리 기술 스택

| 역할 | 기술 요소 | 버전 범위 | 선정 및 설정 이유 |
| :--- | :--- | :--- | :--- |
| **API Framework** | **FastAPI** | `0.100.0` 이상 | 비동기 백그라운드 태스크 처리 지원 및 높은 성능 보장. |
| **Database ORM** | **SQLAlchemy** | `2.0.0` 이상 | 파이썬의 표준 ORM 및 정적 타입 힌트(`Mapped`, `mapped_column`) 완벽 지원. |
| **DB Client Driver** | **psycopg2-binary** | `2.9.0` 이상 | PostgreSQL 연동용 파이썬 C-확장 표준 드라이버. |
| **UUIDv7 Generation** | **uuid6** | `2024.1.0` 이상 | 파이썬 기본 `uuid` 모듈에서 지원하지 않는 UUIDv7 규격 고속 생성 지원. |
| **Rate Limiting** | **slowapi** | `0.1.0` 이상 | FastAPI용 데코레이터 기반 Rate Limiter. 별도 Redis 없이 인메모리(Memory) 방식으로 동작 가능해 MVP 환경에 적합. |

---

## 2. 데이터베이스 커넥션 풀 (Connection Pool) 상세 설정

저사양 데이터베이스 인스턴스 환경을 보수적으로 고려하여 다음과 같이 SQLAlchemy `QueuePool` 매개변수를 지정합니다.

```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://user:password@localhost:5432/dbname"

engine = create_engine(
    DATABASE_URL,
    pool_size=2,          # 커넥션 풀에 상시 유지할 연결 갯수 (Min)
    max_overflow=3,       # 필요시 풀 크기를 초과하여 생성할 수 있는 연결 최대 갯수 (Max=pool_size+max_overflow=5)
    pool_timeout=30.0,    # 커넥션 풀에서 여유 연결을 대기하는 최대 초 시간 (초과 시 Timeout 예외 발생)
    pool_recycle=1800,    # 커넥션 연결 시간 제한 (30분 후 자동 커넥션 재생성하여 커넥션 릭 예외 방지)
    pool_pre_ping=True,   # 커넥션 사용 전 생존 여부를 먼저 점검 (DB 순단 현상 발생 시 유효하지 않은 커넥션 필터링 및 자동 재연결)
)
```

---

## 3. API 속도 제한 (Rate Limiting) 구현 메커니즘

FastAPI 엔드포인트에 `slowapi` 라이브러리를 적용하여 클라이언트 IP 주소를 식별자로 사용하고, 인메모리 기반으로 호출 횟수를 제어합니다.

```python
from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app = FastAPI()
app.state.limiter = limiter

# RateLimitExceeded 예외를 표준 REST Error Schema 형식으로 반환하도록 매핑
@app.exception_handler(RateLimitExceeded)
def custom_rate_limit_handler(request: Request, exc: RateLimitExceeded):
    return JSONResponse(
        status_code=400,
        content={
            "detail": {
                "status": "error",
                "code": "VALIDATION_ERROR",
                "message": f"Rate limit exceeded: {exc.detail}"
            }
        }
    )

# 엔드포인트 데코레이터 적용 예시
# @app.post("/api/v1/jobs")
# @limiter.limit("10/minute")
# async def create_job(request: Request):
#     ...
```
