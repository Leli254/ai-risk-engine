import time
import threading
from collections import defaultdict
from typing import Dict, List


class InMemoryRateLimiter:
    """
    A thread-safe, sliding-window rate limiter for protecting expensive 
    AI endpoints. Implements a self-cleaning mechanism to prevent memory leaks.
    """

    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = window_seconds
        # Thread safety: Ensure atomic updates to the store
        self._lock = threading.Lock()
        self._store: Dict[str, List[float]] = defaultdict(list)
        self._last_cleanup = time.time()

    def is_allowed(self, identifier: str) -> bool:
        with self._lock:
            now = time.time()
            window_start = now - self.window

            # 1. Clean up current user's history
            user_history = [
                t for t in self._store[identifier] if t > window_start]

            # 2. Check threshold
            if len(user_history) >= self.max_requests:
                return False

            # 3. Update state
            user_history.append(now)
            self._store[identifier] = user_history

            # 4. Periodic Global Cleanup (prevent memory leaks)
            # Every 10 minutes, prune users who haven't visited in a while
            if now - self._last_cleanup > 600:
                self._global_prune(now)

            return True

    def _global_prune(self, now: float) -> None:
        """Removes expired entries from the entire store to save memory."""
        cutoff = now - self.window
        # We use list() to avoid 'dictionary changed size during iteration' errors
        for key in list(self._store.keys()):
            if not self._store[key] or max(self._store[key]) < cutoff:
                del self._store[key]
        self._last_cleanup = now


# Singleton instance
limiter = InMemoryRateLimiter(max_requests=5, window_seconds=60)
