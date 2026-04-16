from typing import AsyncGenerator
from fastapi import Depends

import redis.asyncio as aioredis

from app.config import settings
from app.repository import LeaderboardRepository
from app.redis_service import RedisService
from app.postgres_service import PostgresService

# Trạng thái backend đang dùng
current_backend: str = settings.db_backend   # "redis" | "postgres"

# Pool Postgres được khởi tạo 1 lần trong lifespan của main.py
_postgres_pool = None

def set_postgres_pool(pool) -> None:
    global _postgres_pool
    _postgres_pool = pool

def get_postgres_pool():
    return _postgres_pool


# Redis client 
async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:
    client = aioredis.from_url(
        settings.redis_url,
        db=settings.redis_db,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


# Inject đúng service theo current_backend 
async def get_leaderboard_service(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> LeaderboardRepository:
    if current_backend == "postgres":
        pool = get_postgres_pool()
        if pool is None:
            raise RuntimeError("PostgreSQL pool chưa được khởi tạo")
        return PostgresService(pool)
    return RedisService(redis_client)


async def get_redis_service(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> RedisService:
    return RedisService(redis_client)
