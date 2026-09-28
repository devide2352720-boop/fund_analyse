"""Disk-based pickle cache with TTL support."""

import os
import pickle
import time
import threading
from typing import Any, Optional

CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "cache")


class CacheManager:
    """Thread-safe disk cache using pickle serialization."""

    def __init__(self, cache_dir: str = CACHE_DIR):
        self.cache_dir = cache_dir
        self._lock = threading.Lock()
        os.makedirs(self.cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        safe_key = key.replace("/", "_").replace(":", "_").replace(" ", "_")
        return os.path.join(self.cache_dir, f"{safe_key}.pkl")

    def get(self, key: str) -> Optional[Any]:
        """Return cached data if valid, None if missing or expired."""
        path = self._path(key)
        try:
            with self._lock:
                if not os.path.exists(path):
                    return None
                with open(path, "rb") as f:
                    entry = pickle.load(f)
            if entry["ttl"] is not None and time.time() - entry["timestamp"] > entry["ttl"]:
                os.remove(path)
                return None
            return entry["data"]
        except (pickle.UnpicklingError, EOFError, OSError):
            return None

    def set(self, key: str, data: Any, ttl: Optional[int] = None) -> None:
        """Cache data with optional TTL in seconds. None = never expires."""
        path = self._path(key)
        entry = {"timestamp": time.time(), "ttl": ttl, "data": data}
        with self._lock:
            with open(path, "wb") as f:
                pickle.dump(entry, f)

    def clear(self) -> None:
        """Remove all cached files."""
        with self._lock:
            for fname in os.listdir(self.cache_dir):
                if fname.endswith(".pkl"):
                    os.remove(os.path.join(self.cache_dir, fname))

    def clear_expired(self) -> None:
        """Remove only expired entries."""
        now = time.time()
        with self._lock:
            for fname in os.listdir(self.cache_dir):
                if not fname.endswith(".pkl"):
                    continue
                path = os.path.join(self.cache_dir, fname)
                try:
                    with open(path, "rb") as f:
                        entry = pickle.load(f)
                    if entry["ttl"] is not None and now - entry["timestamp"] > entry["ttl"]:
                        os.remove(path)
                except Exception:
                    os.remove(path)


# Module-level singleton
_cache_manager: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
