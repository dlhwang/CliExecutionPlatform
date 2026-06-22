import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from llm.client import LLMClient, LLMClientError, LLMRequest
from llm.parser import ActionPlanParser, LLMPlanRetryableException, LLMPlanValidationError

RETRY_DELAYS_SECONDS = (1.0, 2.0)


class LLMPlanRetryExecutor:
    def __init__(
        self,
        client: LLMClient,
        parser: ActionPlanParser,
        *,
        delays: tuple[float, ...] = RETRY_DELAYS_SECONDS,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        on_attempt: Callable[[int], Any] | None = None,
    ):
        self._client = client
        self._parser = parser
        self._delays = delays
        self._sleep = sleep
        self._on_attempt = on_attempt

    async def generate_actions(
        self,
        request: LLMRequest,
        validation_cb: Callable[[Any], None] | None = None,
    ):
        current_request = request
        for attempt in range(len(self._delays) + 1):
            if self._on_attempt:
                self._on_attempt(attempt + 1)
            try:
                response = await self._client.generate_plan(current_request)
                actions = self._parser.parse_action_plan(response)
                if validation_cb:
                    validation_cb(actions)
                return actions
            except LLMClientError as exc:
                if not exc.retryable or attempt >= len(self._delays):
                    raise
                feedback = "The previous request failed temporarily. Return a valid action plan."
            except LLMPlanRetryableException as exc:
                if attempt >= len(self._delays):
                    raise
                feedback = f"Previous action plan parse failed: {exc.error_position or 'invalid JSON'}"
            except LLMPlanValidationError as exc:
                if exc.status_code == 403 or attempt >= len(self._delays):
                    raise
                feedback = exc.message

            await self._sleep(self._delays[attempt])
            current_request = current_request.with_retry_feedback(feedback)



