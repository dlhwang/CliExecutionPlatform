from typing import Literal, List, Union, Annotated
from pydantic import BaseModel, Field

# -------------------------------------------------------------------
# 1. 개별 액션 DTO 스키마 (Individual Action Schemas)
# -------------------------------------------------------------------

class CreateDirectoryAction(BaseModel):
    """
    지정된 상대 경로에 디렉토리를 생성하는 액션 스키마.
    """
    action: Literal["CREATE_DIRECTORY"] = Field(
        ..., description="액션 타입 식별자"
    )
    path: str = Field(
        ..., min_length=1, description="생성할 디렉토리의 상대 경로"
    )


class WriteFileAction(BaseModel):
    """
    지정된 파일명 및 상대 경로에 소스 코드나 텍스트 콘텐츠를 기록하는 액션 스키마.
    """
    action: Literal["WRITE_FILE"] = Field(
        ..., description="액션 타입 식별자"
    )
    path: str = Field(
        ..., min_length=1, description="작성할 파일의 상대 경로"
    )
    content: str = Field(
        ..., description="기록할 파일의 텍스트 또는 코드 내용"
    )


class RunToolAction(BaseModel):
    """
    허용된 외부 CLI 도구를 인자 배열과 함께 기동하는 액션 스키마.
    """
    action: Literal["RUN_TOOL"] = Field(
        ..., description="액션 타입 식별자"
    )
    tool_name: str = Field(
        ..., min_length=1, description="기동할 도구명 (예: openscad)"
    )
    args: List[str] = Field(
        default_factory=list, description="도구 실행에 넘길 인수 배열"
    )


class CreateArtifactAction(BaseModel):
    """
    임시 작업 영역의 파일을 영구 아티팩트 보관소로 복사하여 다운로드 가능하게 보존하는 액션 스키마.
    """
    action: Literal["CREATE_ARTIFACT"] = Field(
        ..., description="액션 타입 식별자"
    )
    path: str = Field(
        ..., min_length=1, description="영구 아티팩트로 보존할 대상 파일의 상대 경로"
    )

# -------------------------------------------------------------------
# 2. 액션 플랜 판별 통합 유니온 (Discriminated Union Plan)
# -------------------------------------------------------------------

# Pydantic 2.x의 Discriminator 기능을 활용하여 'action' 필드값에 따라 자동 매핑되도록 설계
ActionType = Annotated[
    Union[
        CreateDirectoryAction, 
        WriteFileAction, 
        RunToolAction, 
        CreateArtifactAction
    ],
    Field(discriminator="action")
]

class ActionPlan(BaseModel):
    """
    LLM이 도출한 최종 순차 액션 리스트 래퍼 스키마.
    """
    plan: List[ActionType] = Field(
        ..., description="순서대로 실행할 개별 액션 객체 리스트"
    )
