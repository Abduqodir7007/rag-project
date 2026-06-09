import logging
import time
import json
from typing import Any, Dict, Optional
from datetime import datetime, timezone
from functools import wraps


class JsonFormatter(logging.Formatter):

    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if hasattr(record, "extra_data"):
            log_record.update({"extra_data": record.extra_data})
        return json.dumps(log_record)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.hasHandlers():
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


class MetricsTracker:
    def __init__(self):
        self.total_requests = 0
        self._total_error = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._token_inputs = 0
        self._token_outputs = 0

    def record_request(self, query: str, response: str, cache_hit: bool = False, error: bool = False) -> None:
        self.total_requests += 1
        if error:
            self._total_error += 1
        if cache_hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1
        # implement token counting logic here, for simplicity we use word count as a proxy for tokens
        self._token_inputs += len(query.split())
        self._token_outputs += len(response.split())

    def get_metrics(self) -> Dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_error": self._total_error,
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "token_inputs": self._token_inputs,
            "token_outputs": self._token_outputs,
        }


class RequestTimer:

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed_time = (time.time() - self.start_time) * 1000  # Convert to milliseconds

    @property
    def duration(self) -> float:
        return self.elapsed_time
