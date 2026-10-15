"""Caching layer for HTTP requests and intermediate results."""

import time
import json
import hashlib
from typing import Optional, Any, Dict


class SimpleCache:
    """Thread-safe in-memory cache with TTL support."""
    def __init__(self, default_ttl_seconds: int = 172800):  # 48 hours
        self.default_ttl = default_ttl_seconds
        self._store: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def hash_key(prefix: str, payload: Any) -> str:
        serialized = json.dumps(payload, sort_keys=True, default=str)
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()[:16]
        return f"{prefix}:{digest}"

    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if not entry:
            return None
        if time.time() > entry["expires_at"]:
            del self._store[key]
            return None
        return entry["data"]

    def set(self, key: str, data: Any, ttl_seconds: Optional[int] = None) -> None:
        ttl = ttl_seconds if ttl_seconds is not None else self.default_ttl
        self._store[key] = {
            "data": data,
            "expires_at": time.time() + ttl,
            "created_at": time.time()
        }

    def clear(self) -> None:
        self._store.clear()

    def size(self) -> int:
        # Purge expired on count
        now = time.time()
        keys_to_del = [k for k, v in self._store.items() if now > v["expires_at"]]
        for k in keys_to_del:
            del self._store[k]
        return len(self._store)


# Global cache instance
cache = SimpleCache()
