"""Fixed-window rate limit per client for the API and MCP endpoints.

shortcut: counts per worker process, so with several workers the effective
limit is API_RATE_LIMIT times the worker count; enforce it in the reverse
proxy if that matters.
"""
import threading
import time


class RateLimiter:
    def __init__(self, per_minute):
        self.per_minute = per_minute
        self._lock = threading.Lock()
        self._window = 0
        self._counts = {}

    def allow(self, client):
        """Count one request of client, False once it exceeds the limit."""
        if self.per_minute <= 0:
            return True
        window = int(time.monotonic() // 60)
        with self._lock:
            if window != self._window:
                self._window, self._counts = window, {}
            self._counts[client] = self._counts.get(client, 0) + 1
            return self._counts[client] <= self.per_minute

    @staticmethod
    def retry_after():
        return str(60 - int(time.monotonic()) % 60)
