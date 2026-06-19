import base64
import hashlib
import hmac
import os
from uuid import UUID


class StreamTokenConfigurationError(RuntimeError):
    pass


class StreamTokenService:
    TOKEN_VERSION = "v1"

    def __init__(self, secret: str):
        if not secret or not secret.strip():
            raise StreamTokenConfigurationError(
                "SSE_STREAM_TOKEN_SECRET must be configured."
            )
        self._secret = secret.encode("utf-8")

    @classmethod
    def from_environment(cls) -> "StreamTokenService":
        return cls(os.getenv("SSE_STREAM_TOKEN_SECRET", ""))

    def create_token(self, job_id: UUID) -> str:
        digest = hmac.new(
            self._secret,
            str(job_id).encode("ascii"),
            hashlib.sha256,
        ).digest()
        signature = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
        return f"{self.TOKEN_VERSION}.{signature}"

    def verify_token(self, job_id: UUID, provided_token: str | None) -> bool:
        if not provided_token:
            return False
        expected_token = self.create_token(job_id)
        return hmac.compare_digest(expected_token, provided_token)

