import json
import re
from typing import List
from pydantic import ValidationError
from llm.schemas import ActionPlan, ActionType

class LLMPlanException(Exception):
    """
    LLM 액션 플랜 관련 처리를 수행할 때 발생하는 최상위 커스텀 예외 클래스입니다.
    """
    pass

class LLMPlanRetryableException(LLMPlanException):
    """
    LLM이 생성한 JSON 구문 오류 등 일시적인 문제로 인해 발생하며,
    오케스트레이터에서 LLM 재시도 루프를 수행할 수 있도록 회복 가능한 상세 컨텍스트를 제공하는 예외입니다.
    """
    def __init__(self, message: str, raw_content: str, error_position: str = None):
        super().__init__(message)
        self.message = message
        self.raw_content = raw_content
        self.error_position = error_position

class LLMPlanValidationError(LLMPlanException):
    """
    Pydantic 스키마 필드 검증 실패나 비인가 경로 접근, 미허용 도구 호출과 같은
    보안 정책 위반 등의 즉시 실패용 비회복성 유효성 오류가 감지되었을 때 발생하는 예외입니다.
    """
    def __init__(self, message: str, status_code: int = 400, error_code: str = "VALIDATION_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code

class ActionPlanParser:
    """
    LLM이 마크다운 형식이나 일반 텍스트 형태로 생성한 응답으로부터
    JSON 액션 플랜 데이터를 안전하고 유연하게 추출하여 Pydantic DTO 리스트로 파싱하는 클래스입니다.
    """

    def parse_action_plan(self, text: str) -> List[ActionType]:
        """
        LLM 응답 텍스트를 파싱하여 Pydantic DTO 기반의 검증된 액션 리스트를 반환합니다.

        - Parameter:
          - text: LLM API가 출력한 원본 텍스트 (Markdown 포함 가능)
        - Return:
          - Pydantic DTO (ActionType) 인스턴스들의 리스트
        - Exception:
          - LLMPlanRetryableException: JSON 구문 에러로 파싱 불가시 (재시도용)
          - LLMPlanValidationError: 필드 유효성 조건 위반 시 (즉시 실패용)
        """
        # 1단계: 정규식 기반 ```json block 추출 시도
        json_block_pattern = re.compile(r"```json\s*(.*?)\s*```", re.DOTALL)
        match = json_block_pattern.search(text)
        
        json_str = None
        if match:
            json_str = match.group(1).strip()
        else:
            # 2단계 (Fallback): 첫 [ 와 마지막 ] 인덱스 범위 기반 추출 시도
            start_idx = text.find("[")
            end_idx = text.rfind("]")
            if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
                json_str = text[start_idx:end_idx + 1].strip()
        
        if not json_str:
            raise LLMPlanRetryableException(
                message="Failed to parse LLM response as a valid Action Plan JSON. No JSON block or array structure found.",
                raw_content=text,
                error_position="Entire text search failed"
            )
            
        try:
            json_obj = json.loads(json_str)
        except json.JSONDecodeError as e:
            error_pos = f"line {e.lineno}, col {e.colno}"
            raise LLMPlanRetryableException(
                message="Failed to parse LLM response as a valid Action Plan JSON. Syntax error.",
                raw_content=text,
                error_position=error_pos
            ) from e
            
        try:
            # JSON이 직접 리스트인 경우, ActionPlan 스펙에 맞춰 {"plan": json_obj} 구조로 보정
            if isinstance(json_obj, list):
                plan_data = {"plan": json_obj}
            elif isinstance(json_obj, dict):
                # {"plan": [...]} 형태인 경우 그대로 사용
                plan_data = json_obj
            else:
                raise LLMPlanValidationError(
                    message="Parsed JSON is not a valid list or dictionary structure.",
                    status_code=400,
                    error_code="VALIDATION_ERROR"
                )
                
            validated_plan = ActionPlan.model_validate(plan_data)
            return validated_plan.plan
            
        except ValidationError as e:
            # Pydantic ValidationError를 파싱하기 쉽고 명확한 세부 내용 문자열로 변환
            errors = e.errors()
            err_msgs = []
            for err in errors:
                loc = " -> ".join(str(l) for l in err.get("loc", []))
                msg = err.get("msg", "Unknown error")
                err_msgs.append(f"[{loc}]: {msg}")
            
            detail_msg = "; ".join(err_msgs)
            raise LLMPlanValidationError(
                message=f"Pydantic validation failed: {detail_msg}",
                status_code=400,
                error_code="VALIDATION_ERROR"
            ) from e
