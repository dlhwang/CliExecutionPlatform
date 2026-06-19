import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from sqlalchemy import BigInteger, ForeignKey, String, Text, DateTime, func, Index, JSON, UUID, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from uuid6 import uuid7  # 시간 순 정렬이 가능한 UUIDv7 생성을 위해 사용

from database import Base

class Job(Base):
    """
    비동기 CLI 실행 작업의 기본 메타데이터 및 LLM이 도출한 액션 플랜을 저장하는 ORM 모델.
    - SQLite와 PostgreSQL 양측 호환을 위해 JSON / UUID 표준 타입을 활용합니다.
    """
    __tablename__ = "jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid7
    )
    parent_job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="CREATED", nullable=False)
    action_plan: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # 1대N 관계 매핑
    logs: Mapped[List["EventLog"]] = relationship(
        "EventLog", back_populates="job", cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["Job"]] = relationship(
        "Job", remote_side=[id], back_populates="children"
    )
    children: Mapped[List["Job"]] = relationship("Job", back_populates="parent")


class EventLog(Base):
    """
    특정 Job의 수행 과정에서 발생한 시스템 로그 및 CLI 프로세스의 출력 로그를 저장하는 ORM 모델.
    - SQLite에서 Auto Increment가 정상 적용되도록 BigInteger를 Integer(sqlite용) 변종으로 선언합니다.
    """
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(
        BigInteger().with_variant(Integer, "sqlite"), primary_key=True, autoincrement=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # N대1 관계 매핑
    job: Mapped["Job"] = relationship("Job", back_populates="logs")


# idx_event_logs_job_id_id 결합 인덱스 추가 (특정 Job의 로그를 ID 순서대로 고속 조회 및 Polling 하기 위함)
Index("idx_event_logs_job_id_id", EventLog.job_id, EventLog.id)
