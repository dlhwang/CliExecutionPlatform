import asyncio

from sse.config import MAX_CONNECTIONS


class ConnectionRegistry:
    def __init__(self, max_connections: int = MAX_CONNECTIONS):
        if max_connections < 1:
            raise ValueError("max_connections must be at least 1")
        self._max_connections = max_connections
        self._active_connections = 0
        self._lock = asyncio.Lock()

    async def try_acquire(self) -> bool:
        async with self._lock:
            if self._active_connections >= self._max_connections:
                return False
            self._active_connections += 1
            return True

    async def release(self) -> None:
        async with self._lock:
            if self._active_connections > 0:
                self._active_connections -= 1

    async def active_count(self) -> int:
        async with self._lock:
            return self._active_connections

