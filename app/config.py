from pydantic_settings import BaseSettings
from typing import Literal


class Settings(BaseSettings):
    # Redis
    redis_url: str = "redis://127.0.0.1:6379"
    redis_db: int = 0
    leaderboard_key: str = "leaderboard"

    # PostgreSQL
    postgres_url: str = "postgresql://postgres:password@localhost:5432/leaderboard"

    # Switch: "redis" hoặc "postgres"
    db_backend: Literal["redis", "postgres"] = "redis"

    # Server
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",   
    }


settings = Settings()
