import asyncio
from contextlib import asynccontextmanager

MAX_CONCURRENT_JOBS = 2
QUEUE_WAIT_TIMEOUT_SECONDS = 600.0


class OrchestrationQueueTimeoutError(RuntimeError):
    pass


class OrchestrationConcurrencyGate:
    def __init__(
        self,
        max_concurrent: int = MAX_CONCURRENT_JOBS,
        wait_timeout: float = QUEUE_WAIT_TIMEOUT_SECONDS,
    ):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._wait_timeout = wait_timeout

    @asynccontextmanager
    async def slot(self):
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=self._wait_timeout)
        except asyncio.TimeoutError as exc:
            raise OrchestrationQueueTimeoutError(
                "Orchestration queue wait exceeded the configured timeout."
            ) from exc
        try:
            yield
        finally:
            self._semaphore.release()

