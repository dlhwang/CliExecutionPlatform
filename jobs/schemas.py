from pydantic import BaseModel, Field, ConfigDict
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime

# POST /api/v1/jobs 요청 스키마
class JobCreateRequest(BaseModel):
    prompt: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        examples=["샤오미 워치 S4 충전 도킹스테이션 설계도를 만들어줘"]
    )


class RefinementRequest(JobCreateRequest):
    pass

# Job 기본 응답 스키마
class JobResponse(BaseModel):
    id: UUID
    parent_job_id: Optional[UUID] = None
    prompt: str
    status: str
    action_plan: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime
    stream_url: str
    stream_token: str

    # Pydantic v2 호환 설정 (SQLAlchemy 모델 객체를 Pydantic 모델로 변환)
    model_config = ConfigDict(from_attributes=True)

# API 표준 에러 응답 포맷
class ErrorDetail(BaseModel):
    status: str = Field("error", description="에러 고정 상태 값")
    code: str = Field(..., description="내부 비즈니스 에러 코드 (예: NOT_FOUND, VALIDATION_ERROR, FORBIDDEN_ACCESS)")
    message: str = Field(..., description="사용자 친화적인 에러 설명 메시지")

class ErrorResponse(BaseModel):
    detail: ErrorDetail
