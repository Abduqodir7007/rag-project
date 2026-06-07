from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from datetime import timezone


class ResponseStatus(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


class CharRequest(BaseModel):
    id: int
    messages: str = Field(..., min_length=1, max_length=10000, description="The message of a user to agent")
    thread_id: str = Field(default="default", description="The thread id of the conversation")


class CharResponse(BaseModel):
    id: int
    response: str = Field(..., description="The response of the agent to user")
    thread_id: str = Field(default="default", description="The thread id of the conversation")
    model_used: str = Field(..., description="The model used to generate the response")
    cached: bool = Field(default=False, description="Whether the response is from cache")
    processing_time: float = Field(default=0.0, description="The processing time of the request in seconds")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="The timestamp of the response"
    )


class HealthResponse(BaseModel):
    status: ResponseStatus = Field(default=ResponseStatus.SUCCESS, description="The health status of the application")
    version: str = "1.0.0"
    environment: str = Field(..., description="The environment the application is running in")
    checks: dict = {}
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="The timestamp of the health check"
    )


class MetricsResponse(BaseModel):
    total_requests: int = Field(default=0, description="The total number of requests processed")
    total_errors: int = Field(default=0, description="The total number of errors encountered")
    error_rate: float = Field(default=0.0, description="The error rate of the application")
    avg_latency: float = Field(default=0.0, description="The average latency of the requests in seconds")
    cache_hit_rate: float = Field(default=0.0, description="The cache hit rate of the application")
    total_input_tokens: int = Field(default=0, description="The total number of input tokens processed")
    total_output_tokens: int = Field(default=0, description="The total number of output tokens generated")


class ErrorResponse(BaseModel):
    error: str
    details: str | None = None
    request_id: str | None = None
