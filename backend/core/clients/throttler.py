import asyncio
import time


class TokenBucketThrottler:
    def __init__(self, interval: float, max_backoff_steps: int = 3):
        self._base_interval = interval
        self._current_interval = interval
        self._max_backoff_steps = max_backoff_steps
        self._backoff_count = 0
        self._last_request_time = 0.0
        self._lock = asyncio.Lock()

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request_time
            wait_time = self._current_interval - elapsed
            if wait_time > 0:
                await asyncio.sleep(wait_time)
            self._last_request_time = time.monotonic()

    def backoff(self) -> None:
        if self._backoff_count < self._max_backoff_steps:
            self._current_interval *= 2
            self._backoff_count += 1

    def reset_backoff(self) -> None:
        self._current_interval = self._base_interval
        self._backoff_count = 0

    @property
    def current_interval(self) -> float:
        return self._current_interval
