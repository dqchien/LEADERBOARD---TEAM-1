import redis.asyncio as aioredis
from typing import Optional
from app.config import settings

LEADERBOARD_KEY = settings.leaderboard_key


def _user_hash_key(user_id: str) -> str:
    return f"user:{user_id}"


def validate_score(score) -> None:
    if score is None:
        raise ValueError("Score khong duoc la None")
    if not isinstance(score, (int, float)):
        raise TypeError("Score phai la so")
    if score <= 0:
        raise ValueError("Score phai > 0")


def validate_user_id(user_id) -> None:
    if not user_id or not isinstance(user_id, str):
        raise ValueError("user_id khong hop le")
    if not user_id.strip():
        raise ValueError("user_id khong duoc rong")


LUA_UPDATE_AND_RANK = """
local new_score = redis.call('ZINCRBY', KEYS[1], ARGV[1], ARGV[2])
local rank = redis.call('ZREVRANK', KEYS[1], ARGV[2])
return {new_score, rank}
"""


class RedisService:
    def __init__(self, redis_client: aioredis.Redis):
        self.r = redis_client

    async def update_score(self, user_id: str, score: float) -> dict:
        validate_user_id(user_id)
        validate_score(score)
        result = await self.r.eval(
            LUA_UPDATE_AND_RANK, 1, LEADERBOARD_KEY, score, user_id,
        )
        new_score = float(result[0])
        rank = int(result[1]) + 1
        return {"user_id": user_id, "new_total_score": new_score, "rank": rank}

    async def get_top_n(self, n: int) -> list[dict]:
        top_users = await self.r.zrevrange(LEADERBOARD_KEY, 0, n - 1, withscores=True)
        result = []
        for rank_index, (user_id, score) in enumerate(top_users, start=1):
            user_data = await self.get_user(user_id)
            result.append({
                "rank": rank_index,
                "user_id": user_id,
                "score": score,
                "name": user_data.get("name", user_id),
                "avatar": user_data.get("avatar", "default.png"),
            })
        return result

    async def get_rank(self, user_id: str) -> Optional[int]:
        validate_user_id(user_id)
        rank = await self.r.zrevrank(LEADERBOARD_KEY, user_id)
        return rank + 1 if rank is not None else None

    async def get_score(self, user_id: str) -> Optional[float]:
        score = await self.r.zscore(LEADERBOARD_KEY, user_id)
        return float(score) if score is not None else None

    async def get_total_users(self) -> int:
        return await self.r.zcard(LEADERBOARD_KEY)

    async def get_user(self, user_id: str) -> dict:
        return await self.r.hgetall(_user_hash_key(user_id))

    async def create_user(self, user_id: str, name: str, avatar: str) -> None:
        validate_user_id(user_id)
        await self.r.hset(_user_hash_key(user_id), mapping={"name": name, "avatar": avatar})

    async def get_rank_info(self, user_id: str) -> Optional[dict]:
        rank = await self.get_rank(user_id)
        if rank is None:
            return None
        score = await self.get_score(user_id)
        user_data = await self.get_user(user_id)
        return {
            "user_id": user_id,
            "rank": rank,
            "score": score,
            "name": user_data.get("name", user_id),
            "avatar": user_data.get("avatar", "default.png"),
        }