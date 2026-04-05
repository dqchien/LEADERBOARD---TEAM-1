from fastapi import APIRouter, HTTPException, Query, Depends
import redis.asyncio as aioredis

from app.models import (
    UpdateScoreRequest, UpdateScoreResponse,
    LeaderboardResponse, UserRankEntry, RankResponse,
)
from app.dependencies import get_redis_service, get_redis_client
from app.redis_service import RedisService
from app.websocket_manager import publish_update

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


@router.post("/score", response_model=UpdateScoreResponse, summary="Cap nhat diem user")
async def update_score(
    payload: UpdateScoreRequest,
    svc: RedisService = Depends(get_redis_service),
    redis_client: aioredis.Redis = Depends(get_redis_client),
):
    try:
        result = await svc.update_score(payload.user_id, payload.score)
        if payload.name or payload.avatar:
            existing = await svc.get_user(payload.user_id)
            await svc.create_user(
                user_id=payload.user_id,
                name=payload.name or existing.get("name", payload.user_id),
                avatar=payload.avatar or existing.get("avatar", "default.png"),
            )
        await publish_update(redis_client, {
            "event": "score_updated",
            "user_id": payload.user_id,
            "new_total_score": result["new_total_score"],
            "rank": result["rank"],
        })
        return UpdateScoreResponse(
            user_id=payload.user_id,
            new_total_score=result["new_total_score"],
            rank=result["rank"],
            message=f"Cap nhat thanh cong! +{payload.score} diem",
        )
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")


@router.get("/top", response_model=LeaderboardResponse, summary="Top N bang xep hang")
async def get_top_leaderboard(
    n: int = Query(default=10, ge=1, le=100),
    svc: RedisService = Depends(get_redis_service),
):
    try:
        top_data = await svc.get_top_n(n)
        total = await svc.get_total_users()
        return LeaderboardResponse(
            total_users=total,
            top_n=len(top_data),
            leaderboard=[UserRankEntry(**entry) for entry in top_data],
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")


@router.get("/rank/{user_id}", response_model=RankResponse, summary="Hang cua mot user")
async def get_user_rank(
    user_id: str,
    svc: RedisService = Depends(get_redis_service),
):
    try:
        info = await svc.get_rank_info(user_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' chua co diem")
        return RankResponse(**info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Redis error: {str(e)}")