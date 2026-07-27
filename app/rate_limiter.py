import threading
import time

from app.config import settings

# How many allow() calls between sweeps for expired entries. Without this,
# self._windows grows by one entry per distinct key ever seen and never
# shrinks, even long after that key's window has expired — an unbounded
# memory leak over a long-running process's lifetime.
_CLEANUP_INTERVAL_CALLS = 1000


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = {}
        self._calls_since_cleanup = 0

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            self._cleanup_if_due(now)
            window_start, count = self._windows.get(key, (0.0, 0))
            if now - window_start >= self.window_seconds:
                self._windows[key] = (now, 1)
                return True
            if count < self.max_requests:
                self._windows[key] = (window_start, count + 1)
                return True
            return False

    def _cleanup_if_due(self, now: float) -> None:
        self._calls_since_cleanup += 1
        if self._calls_since_cleanup < _CLEANUP_INTERVAL_CALLS:
            return
        self._calls_since_cleanup = 0
        expired_keys = [
            key for key, (window_start, _) in self._windows.items()
            if now - window_start >= self.window_seconds
        ]
        for key in expired_keys:
            del self._windows[key]


rate_limiter = FixedWindowRateLimiter(max_requests=settings.rate_limit_per_minute)
