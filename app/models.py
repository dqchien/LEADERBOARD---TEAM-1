from pydantic import BaseModel, Field, field_validator
from typing import Optional


# ─── REQUESTS ─────────────────────────────────────────────────────────────────

class UpdateScoreRequest(BaseModel):
    """Body cho POST /leaderboard/score"""
    user_id: str = Field(..., examples=["user_1"], description="ID của user")
    score: float = Field(..., gt=0, examples=[50.0], description="Điểm cộng thêm (phải > 0)")
    name: Optional[str] = Field(None, examples=["Hiền"], description="Tên hiển thị (tuỳ chọn)")
    avatar: Optional[str] = Field(None, examples=["hien.png"], description="Tên file avatar")

    @field_validator("user_id")
    @classmethod
    def user_id_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("user_id không được rỗng")
        return v.strip()

    @field_validator("score")
    @classmethod
    def score_positive(cls, v: float) -> float:
        # gt=0 trong Field đã bắt, validator này để message rõ hơn
        if v <= 0:
            raise ValueError("Score phải > 0")
        return v


# ─── RESPONSES ────────────────────────────────────────────────────────────────

class UpdateScoreResponse(BaseModel):
    """Response sau khi cập nhật điểm thành công."""
    user_id: str
    new_total_score: float
    rank: int
    message: str


class UserRankEntry(BaseModel):
    """1 dòng trong bảng xếp hạng."""
    rank: int
    user_id: str
    name: str
    avatar: str
    score: float


class LeaderboardResponse(BaseModel):
    """Response cho GET /leaderboard/top"""
    total_users: int
    top_n: int
    leaderboard: list[UserRankEntry]


class RankResponse(BaseModel):
    """Response cho GET /leaderboard/rank/{user_id}"""
    user_id: str
    rank: int
    score: float
    name: str
    avatar: str


class HealthResponse(BaseModel):
    status: str
    redis: str
    message: str