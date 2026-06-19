import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# 로컬 .env 파일 환경 변수 로드
load_dotenv()

# 환경 변수로부터 데이터베이스 URL 로드 (기본값은 로컬 PostgreSQL)
DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://postgres:postgres@localhost:5432/cli_platform"
)

# PostgreSQL인 경우 KST 타임존 적용, SQLite 등 타임존 옵션을 지원하지 않는 DB는 제외
connect_args = {}
if DATABASE_URL.startswith("postgresql"):
    connect_args = {"options": "-c timezone=Asia/Seoul"}

# SQLAlchemy 엔진 생성 (비기능 설계에 정의된 Connection Pool 매개변수 적용)
engine = create_engine(
    DATABASE_URL,
    pool_size=2,          # 상시 유지할 커넥션 수
    max_overflow=3,       # 필요시 임시 허용할 최대 추가 커넥션 수 (Max = 2 + 3 = 5)
    pool_timeout=30.0,    # 커넥션 획득 대기 타임아웃
    pool_recycle=1800,    # 커넥션 재사용 한도 시간 (30분)
    pool_pre_ping=True,   # 커넥션 생존 사전 확인 활성화 (DB 순단 현상 방어)
    connect_args=connect_args,
)

# 데이터베이스 세션 생성기
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ORM 선언적 베이스 클래스
Base = declarative_base()

# FastAPI 의존성 주입용 DB 세션 제너레이터
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
