from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    redis_url: str = "redis://127.0.0.1:6379"
    redis_db: int = 0
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    leaderboard_key: str = "leaderboard"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()