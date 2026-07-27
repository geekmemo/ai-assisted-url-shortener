import threading
import time
from collections import defaultdict

from app.config import settings


class FixedWindowRateLimiter:
    def __init__(self, max_requests: int, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._lock = threading.Lock()
        self._windows: dict[str, tuple[float, int]] = defaultdict(lambda: (0.0, 0))

    def allow(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            window_start, count = self._windows[key]
            if now - window_start >= self.window_seconds:
                self._windows[key] = (now, 1)
                return True
            if count < self.max_requests:
                self._windows[key] = (window_start, count + 1)
                return True
            return False


rate_limiter = FixedWindowRateLimiter(max_requests=settings.rate_limit_per_minute)
