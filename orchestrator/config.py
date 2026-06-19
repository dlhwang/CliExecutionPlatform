import os
from dataclasses import dataclass
from urllib.parse import urlparse


class OrchestratorConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class OrchestratorConfig:
    endpoint: str
    api_key: str
    model: str
    environment: str

    @classmethod
    def from_environment(cls) -> "OrchestratorConfig":
        environment = os.getenv("APP_ENV", "development").lower()
        endpoint = os.getenv("LLM_ENDPOINT", "http://localhost:11434/api/generate")
        api_key = os.getenv("LLM_API_KEY", "development-only")
        model = os.getenv("LLM_MODEL", "local-model")
        if environment == "production" and (
            not os.getenv("LLM_ENDPOINT")
            or not os.getenv("LLM_API_KEY")
            or not os.getenv("LLM_MODEL")
        ):
            raise OrchestratorConfigurationError("Production LLM settings are incomplete.")
        cls._validate_endpoint(endpoint, environment)
        return cls(endpoint, api_key, model, environment)

    @staticmethod
    def _validate_endpoint(endpoint: str, environment: str) -> None:
        parsed = urlparse(endpoint)
        if parsed.username or parsed.password or parsed.fragment:
            raise OrchestratorConfigurationError("LLM endpoint contains forbidden URL parts.")
        if parsed.scheme == "https" and parsed.hostname:
            return
        loopback_hosts = {"localhost", "127.0.0.1", "::1"}
        if environment != "production" and parsed.scheme == "http" and parsed.hostname in loopback_hosts:
            return
        raise OrchestratorConfigurationError("LLM endpoint must use an approved HTTPS or loopback URL.")

