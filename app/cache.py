import hashlib
import time
from typing import Any, Dict, Optional


class ResponseCache:

    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self.hits = 0
        self.misses = 0

    def _generate_cache_key(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()

    def get(self, query: str) -> Optional[Any]:
        key = self._generate_cache_key(query)
        entry = self._cache.get(key)

        if entry and (time.time() - entry["timestamp"] < self.ttl):
            self.hits += 1
            return entry["response"]
        elif entry:
            del self._cache[key]  # Remove expired entry
            self.misses += 1
        return None

    def set(self, query: str, response: Any) -> None:
        key = self._generate_cache_key(query)
        self._cache[key] = {"response": response, "timestamp": time.time()}

    def cache_stats(self) -> Dict[str, int]:
        return {"hits": self.hits, "misses": self.misses, "size": len(self._cache)}
