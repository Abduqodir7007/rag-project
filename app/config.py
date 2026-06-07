from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):

    APP_ENV: str = "development"
    PRIMARY_MODEL: str = "gemini-2.5-flash"
    GEMINI_API_KEY: str
    LANGCHAIN_API_KEY: str
    LANGCHAIN_TRACING_V2: bool = False
    CACHE_TTL: int = 3600
    LOG_LEVEL: str = "INFO"
    MAX_RETRIES: int = 3

    model_config = {"env_file": ".env"}

    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"


@lru_cache()
def get_settings() -> Settings:
    # Cache the settings and return the same instance on subsequent calls
    return Settings()
