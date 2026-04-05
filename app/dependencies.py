from typing import AsyncGenerator

import redis.asyncio as aioredis
from fastapi import Depends
from app.config import settings
from app.redis_service import RedisService


async def get_redis_client() -> AsyncGenerator[aioredis.Redis, None]:  # FIX: đổi return type
    client = aioredis.from_url(
        settings.redis_url,
        db=settings.redis_db,
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


async def get_redis_service(
    redis_client: aioredis.Redis = Depends(get_redis_client),
) -> RedisService:
    return RedisService(redis_client)