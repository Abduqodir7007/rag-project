import time
import logging
import os
from contextlib import contextmanager, asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from langsmith import traceable
from dotenv import load_dotenv
from app.monitoring import get_logger, MetricsTracker, RequestTimer

from app.config import get_settings
from app.agent import Agent
from app.models import ChatResponse, CharRequest, HealthResponse, MetricsResponse, ErrorResponse, ResponseStatus
from app.security import SecurityManager
from app.cache import ResponseCache

logger = get_logger()
cache: ResponseCache = None
agent: Agent = None
security_manager: SecurityManager = None
metrics: MetricsTracker = None


@asynccontextmanager
async def lifespan():
    global cache, agent, security_manager, metrics
    settings = get_settings()
    logger.info("Initializing application components...")

    security_manager = SecurityManager()
    cache = ResponseCache(ttl=settings.CACHE_TTL)
    agent = Agent()
    metrics = MetricsResponse()

    logger.info("Application components initialized successfully.")
    yield
    # Shutdown logic can be added here if needed
    logger.info("Shutting down application...")


limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="RAG FastAPI", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):
    return {
        "error": "Rate limit exceeded",
        "details": f"You have exceeded the allowed number of requests. Please try again later.",
    }


@app.post(
    "/chat", response_model=ChatResponse, responses={400: {"model": ErrorResponse}, 401: {"model": ErrorResponse}}
)
@limiter.limit("5/minute")
@traceable(name="chat_endpoint")
async def chat_endpoint(request: Request, char_request: CharRequest):
    with RequestTimer() as timer:
        sucurity_notes = []

        is_clean, clean_messages, notes = security_manager.validate_query(char_request.messages)

        if not is_clean:
            sucurity_notes.extend(notes)
            logger.warning(f"Security validation failed for request {char_request.id}: {notes}")
            metrics.record_request(char_request.messages, "", cache_hit=False, error=True)
            raise HTTPException(status_code=400, detail={"error": "Invalid input", "details": notes})

        cached_response = cache.get(clean_messages)

        if cached_response:
            metrics.record_request(char_request.messages, cached_response, cache_hit=True)
            logger.info(f"Cache hit for request {char_request.id}")
            return ChatResponse(
                id=char_request.id,
                response=cached_response,
                thread_id=char_request.thread_id,
                model_used="cache",
                cached=True,
                processing_time=timer.duration,
            )
        try:
            agent_response = agent.invoke(clean_messages)
        except Exception as e:
            logger.error(f"Error occurred while invoking agent for request {char_request.id}: {e}")
            metrics.record_request(char_request.messages, "", cache_hit=False, error=True)
            raise HTTPException(status_code=500, detail={"error": "Internal server error"})

        clean_response, output_warnings = security_manager.validate_response(agent_response["response"])
        sucurity_notes.extend(output_warnings)
        cache.set(clean_messages, clean_response)

        metrics.record_request(char_request.messages, clean_response, cache_hit=False, error=False)
        return ChatResponse(
            id=char_request.id,
            response=clean_response,
            thread_id=char_request.thread_id,
            model_used=agent_response.get("model_used", "unknown"),
            cached=False,
            processing_time=timer.duration,
        )


@app.get("/health", response_model=HealthResponse)
async def health_check():

    settings = get_settings()

    checks = {
        "agent": agent is not None,
        "cache": cache is not None,
        "security_manager": security_manager is not None,
    }
    status = all(checks.values())
    return HealthResponse(
        status=ResponseStatus.SUCCESS if status else ResponseStatus.ERROR,
        environment=settings.APP_ENV,
        checks=checks,
    )


@app.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    current_metrics = metrics.get_metrics()
    error_rate = (
        (current_metrics["total_error"] / current_metrics["total_requests"])
        if current_metrics["total_requests"] > 0
        else 0.0
    )
    cache_hit_rate = (
        (current_metrics["cache_hits"] / current_metrics["total_requests"])
        if current_metrics["total_requests"] > 0
        else 0.0
    )

    return MetricsResponse(
        total_requests=current_metrics["total_requests"],
        total_errors=current_metrics["total_error"],
        error_rate=error_rate,
        cache_hit_rate=cache_hit_rate,
        total_input_tokens=current_metrics["token_inputs"],
        total_output_tokens=current_metrics["token_outputs"],
    )


@app.get("/cache/stats")
async def get_cache_stats():
    return cache.cache_stats ()
