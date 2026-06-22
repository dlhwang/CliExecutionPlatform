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
        if "chat/completions" in self._endpoint:
            prompt_content = request.prompt
            if request.context:
                context_str = "\n".join(f"[{filename}]:\n{content}" for filename, content in request.context.items())
                prompt_content += f"\n\nContext files:\n{context_str}"
            if request.retry_feedback:
                prompt_content += f"\n\nRetry Feedback:\n{request.retry_feedback}"

            system_prompt = (
                "You are an assistant that plans file operations and tool executions to solve user requests.\n"
                f"You must generate a list of actions. Allowed actions: {', '.join(request.allowed_actions)}.\n"
                "Your response must be a JSON array containing the action plan inside a ```json ``` block, or just the JSON array itself.\n\n"
                "STRICT JSON SCHEMA — use EXACTLY these field names, no variations:\n\n"
                "CREATE_DIRECTORY:\n"
                '  { "action": "CREATE_DIRECTORY", "path": "relative/directory/path" }\n\n'
                "WRITE_FILE:\n"
                '  { "action": "WRITE_FILE", "path": "relative/file/path.ext", "content": "file content here" }\n\n'
                "RUN_TOOL (IMPORTANT: field name is tool_name, NOT tool; field name is args, NOT inputs or parameters):\n"
                '  { "action": "RUN_TOOL", "tool_name": "openscad", "args": ["-o", "output.stl", "model.scad"] }\n'
                "  NOTE: tool_name MUST be exactly \"openscad\". No other tools are permitted.\n"
                "  OPENSCAD CLI USAGE: openscad -o <output_file> <input_file.scad>\n"
                "    - Use '-o' for output file (NOT '--output', NOT '--o')\n"
                "    - Input .scad file is a positional argument (last argument, no flag prefix)\n"
                "    - Valid output extensions: stl, off, amf, 3mf, csg, dxf, svg, pdf, png\n"
                "    - Example for STL: [\"-o\", \"output.stl\", \"model.scad\"]\n"
                "    - Example for PNG: [\"-o\", \"preview.png\", \"--render\", \"model.scad\"]\n\n"
                "CREATE_ARTIFACT:\n"
                '  { "action": "CREATE_ARTIFACT", "path": "relative/file/path.ext" }\n\n'
                "RULES:\n"
                "- All file paths MUST be relative (no leading / or ../)\n"
                "- Do NOT invent new field names — use only the fields shown above\n"
                "- The JSON array must be the only output inside the ```json ``` block\n"
                "- For WRITE_FILE actions targeting .scad files, the \"content\" string MUST follow these strict OpenSCAD rules:\n"
                "  * Do NOT use Markdown code fences (e.g. ``` or ```scad) inside the scad content itself.\n"
                "  * Do NOT include prose, conversational prefixes or explanations (e.g. \"Here is\", \"The following\", \"Below is\", \"아래는\", \"다음은\", \"다음 코드는\") inside the scad content.\n"
                "  * Do NOT use vector property access (.x, .y, .z). Access vector indices with bracket syntax ONLY (e.g. v[0], v[1], v[2]).\n"
                "  * Do NOT use single quotes (') for strings; always use double quotes (\").\n"
                "  * OpenSCAD trigonometric functions use degrees directly; do NOT use radian conversion formulas (180 / PI or PI / 180).\n"
                "  * The content must be non-empty and must contain valid OpenSCAD constructs (e.g. module, polyhedron, cube, sphere, translate)."
            )

            payload = {
                "model": self._model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt_content}
                ]
            }
        else:
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
            if "choices" in document and len(document["choices"]) > 0:
                content = document["choices"][0]["message"]["content"]
            else:
                content = document["content"]
            if not isinstance(content, str):
                raise TypeError("content must be a string")
            return content
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
            raise LLMClientError("LLM endpoint returned an invalid response.", retryable=False) from exc

