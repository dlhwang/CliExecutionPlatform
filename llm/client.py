import json
from dataclasses import dataclass, replace
from typing import Protocol

import httpx

MAX_LLM_RESPONSE_BYTES = 5 * 1024 * 1024
LLM_TIMEOUT_SECONDS = 120.0


@dataclass(frozen=True)
class LLMRequest:
    prompt: str
    context: dict[str, str]
    allowed_actions: tuple[str, ...]
    retry_feedback: str | None = None

    def with_retry_feedback(self, feedback: str) -> "LLMRequest":
        return replace(self, retry_feedback=feedback)


class LLMClient(Protocol):
    async def generate_plan(self, request: LLMRequest) -> str: ...


class LLMClientError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool):
        super().__init__(message)
        self.retryable = retryable


class LLMResponseTooLargeError(LLMClientError):
    def __init__(self):
        super().__init__("LLM response exceeded the configured size limit.", retryable=False)


class HttpLLMClient:
    def __init__(
        self,
        client: httpx.AsyncClient,
        endpoint: str,
        api_key: str,
        model: str,
        *,
        max_response_bytes: int = MAX_LLM_RESPONSE_BYTES,
        timeout_seconds: float = LLM_TIMEOUT_SECONDS,
    ):
        self._client = client
        self._endpoint = endpoint
        self._api_key = api_key
        self._model = model
        self._max_response_bytes = max_response_bytes
        self._timeout = httpx.Timeout(timeout_seconds)

    async def generate_plan(self, request: LLMRequest) -> str:
        payload = {
            "model": self._model,
            "prompt": request.prompt,
            "context": request.context,
            "allowed_actions": list(request.allowed_actions),
            "retry_feedback": request.retry_feedback,
        }
        try:
            async with self._client.stream(
                "POST",
                self._endpoint,
                headers={"Authorization": f"Bearer {self._api_key}"},
                json=payload,
                timeout=self._timeout,
                follow_redirects=False,
            ) as response:
                if 300 <= response.status_code < 400:
                    raise LLMClientError("LLM endpoint redirect was rejected.", retryable=False)
                if response.status_code >= 400:
                    retryable = (
                        response.status_code in {408, 429}
                        or response.status_code >= 500
                    )
                    raise LLMClientError(
                        f"LLM endpoint returned HTTP {response.status_code}.",
                        retryable=retryable,
                    )

                declared_length = response.headers.get("content-length")
                if declared_length and int(declared_length) > self._max_response_bytes:
                    raise LLMResponseTooLargeError()

                body = bytearray()
                async for chunk in response.aiter_bytes():
                    body.extend(chunk)
                    if len(body) > self._max_response_bytes:
                        raise LLMResponseTooLargeError()
        except (httpx.TimeoutException, httpx.NetworkError) as exc:
            raise LLMClientError("LLM endpoint is temporarily unavailable.", retryable=True) from exc
        except LLMClientError:
            raise
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise LLMClientError("LLM endpoint returned an invalid response.", retryable=False) from exc

        try:
            document = json.loads(bytes(body).decode("utf-8"))
            content = document["content"]
            if not isinstance(content, str):
                raise TypeError("content must be a string")
            return content
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LLMClientError("LLM endpoint returned an invalid response.", retryable=False) from exc

