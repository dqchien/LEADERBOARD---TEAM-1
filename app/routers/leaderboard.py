from fastapi import APIRouter, HTTPException, Query, Depends
import redis.asyncio as aioredis

from app.models import (
    UpdateScoreRequest, UpdateScoreResponse,
    LeaderboardResponse, UserRankEntry, RankResponse,
)
from app.dependencies import (
    get_leaderboard_service, get_redis_client,
    current_backend, set_postgres_pool, get_postgres_pool,
)
import app.dependencies as deps
from app.repository import LeaderboardRepository
from app.websocket_manager import publish_update
from app.redis_service import LEADERBOARD_KEY

router = APIRouter(prefix="/leaderboard", tags=["Leaderboard"])


# Update score
@router.post("/score", response_model=UpdateScoreResponse, summary="Cap nhat diem user")
async def update_score(
    payload: UpdateScoreRequest,
    svc: LeaderboardRepository = Depends(get_leaderboard_service),
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
        raise HTTPException(status_code=500, detail=str(e))


# Top N 
@router.get("/top", response_model=LeaderboardResponse, summary="Top N bang xep hang")
async def get_top_leaderboard(
    n: int = Query(default=10, ge=1, le=100),
    svc: LeaderboardRepository = Depends(get_leaderboard_service),
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
        raise HTTPException(status_code=500, detail=str(e))


# Reset 
@router.delete("/reset", summary="Xoa toan bo du lieu leaderboard")
async def reset_leaderboard(
    svc: LeaderboardRepository = Depends(get_leaderboard_service),
    redis_client: aioredis.Redis = Depends(get_redis_client),
):
    try:
        count = await svc.reset()
        await publish_update(redis_client, {"event": "leaderboard_reset"})
        return {"message": f"Da xoa {count} users"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Rank of 1 user 
@router.get("/rank/{user_id}", response_model=RankResponse, summary="Hang cua mot user")
async def get_user_rank(
    user_id: str,
    svc: LeaderboardRepository = Depends(get_leaderboard_service),
):
    try:
        info = await svc.get_rank_info(user_id)
        if info is None:
            raise HTTPException(status_code=404, detail=f"User '{user_id}' chua co diem")
        return RankResponse(**info)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Switch backend
@router.post("/switch-backend", summary="Chuyen doi giua Redis va PostgreSQL")
async def switch_backend(target: str = Query(..., pattern="^(redis|postgres)$")):
    """
    Chuyển đổi backend đang dùng mà không cần restart server.
    - target=redis   → dùng Redis (nhanh, RAM)
    - target=postgres → dùng PostgreSQL (bền, ổ đĩa)
    """
    if target == "postgres" and get_postgres_pool() is None:
        raise HTTPException(
            status_code=503,
            detail="PostgreSQL chưa kết nối. Kiểm tra POSTGRES_URL trong .env",
        )
    deps.current_backend = target
    return {
        "message": f"Da chuyen sang {target}",
        "current_backend": deps.current_backend,
    }


@router.get("/current-backend", summary="Xem backend dang dung")
async def get_current_backend():
    return {"current_backend": deps.current_backend}
