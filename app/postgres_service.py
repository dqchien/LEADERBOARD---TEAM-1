"""
app/postgres_service.py
────────────────────────
Implement LeaderboardRepository dùng PostgreSQL (asyncpg).
Chậm hơn Redis một chút nhưng dữ liệu tồn tại vĩnh viễn trên ổ đĩa.

Schema (tự tạo khi khởi động):
  lb_users  (user_id PK, name, avatar)
  lb_scores (user_id PK FK, score)
"""

import asyncpg
from typing import Optional
from app.repository import LeaderboardRepository


# SQL tạo bảng nếu chưa có
INIT_SQL = """
CREATE TABLE IF NOT EXISTS lb_users (
    user_id TEXT PRIMARY KEY,
    name    TEXT NOT NULL DEFAULT '',
    avatar  TEXT NOT NULL DEFAULT 'default.png'
);

CREATE TABLE IF NOT EXISTS lb_scores (
    user_id TEXT PRIMARY KEY REFERENCES lb_users(user_id) ON DELETE CASCADE,
    score   DOUBLE PRECISION NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_lb_scores_score ON lb_scores (score DESC);
"""


class PostgresService(LeaderboardRepository):
    def __init__(self, pool: asyncpg.Pool):
        self.pool = pool

    # ── Khởi tạo schema ──────────────────────────────────────────────────────
    @classmethod
    async def create_pool(cls, dsn: str) -> asyncpg.Pool:
        return await asyncpg.create_pool(dsn, min_size=2, max_size=10)

    async def init_schema(self) -> None:
        """Tạo bảng nếu chưa có. Gọi 1 lần khi khởi động."""
        async with self.pool.acquire() as conn:
            await conn.execute(INIT_SQL)

    # ── Implement interface ───────────────────────────────────────────────────
    async def update_score(self, user_id: str, score: float) -> dict:
        async with self.pool.acquire() as conn:
            # Đảm bảo user tồn tại trong lb_users trước
            await conn.execute(
                "INSERT INTO lb_users (user_id) VALUES ($1) ON CONFLICT DO NOTHING",
                user_id,
            )
            # Upsert điểm: nếu có rồi thì cộng thêm, chưa có thì insert
            new_score = await conn.fetchval(
                """
                INSERT INTO lb_scores (user_id, score) VALUES ($1, $2)
                ON CONFLICT (user_id) DO UPDATE
                    SET score = lb_scores.score + EXCLUDED.score
                RETURNING score
                """,
                user_id, score,
            )
            # Rank = số user có điểm cao hơn + 1
            rank = await conn.fetchval(
                "SELECT COUNT(*) + 1 FROM lb_scores WHERE score > $1",
                new_score,
            )
            return {"user_id": user_id, "new_total_score": float(new_score), "rank": int(rank)}

    async def get_top_n(self, n: int) -> list[dict]:
        async with self.pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT s.user_id, s.score,
                       COALESCE(u.name, s.user_id) AS name,
                       COALESCE(u.avatar, 'default.png') AS avatar,
                       ROW_NUMBER() OVER (ORDER BY s.score DESC) AS rank
                FROM lb_scores s
                LEFT JOIN lb_users u USING (user_id)
                ORDER BY s.score DESC
                LIMIT $1
                """,
                n,
            )
            return [dict(r) for r in rows]

    async def get_rank(self, user_id: str) -> Optional[int]:
        async with self.pool.acquire() as conn:
            score = await conn.fetchval(
                "SELECT score FROM lb_scores WHERE user_id = $1", user_id,
            )
            if score is None:
                return None
            rank = await conn.fetchval(
                "SELECT COUNT(*) + 1 FROM lb_scores WHERE score > $1", score,
            )
            return int(rank)

    async def get_score(self, user_id: str) -> Optional[float]:
        async with self.pool.acquire() as conn:
            score = await conn.fetchval(
                "SELECT score FROM lb_scores WHERE user_id = $1", user_id,
            )
            return float(score) if score is not None else None

    async def get_total_users(self) -> int:
        async with self.pool.acquire() as conn:
            return await conn.fetchval("SELECT COUNT(*) FROM lb_scores")

    async def get_user(self, user_id: str) -> dict:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT name, avatar FROM lb_users WHERE user_id = $1", user_id,
            )
            return dict(row) if row else {}

    async def create_user(self, user_id: str, name: str, avatar: str) -> None:
        async with self.pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO lb_users (user_id, name, avatar) VALUES ($1, $2, $3)
                ON CONFLICT (user_id) DO UPDATE SET name = $2, avatar = $3
                """,
                user_id, name, avatar,
            )

    async def get_rank_info(self, user_id: str) -> Optional[dict]:
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT s.user_id, s.score,
                       COALESCE(u.name, s.user_id) AS name,
                       COALESCE(u.avatar, 'default.png') AS avatar
                FROM lb_scores s
                LEFT JOIN lb_users u USING (user_id)
                WHERE s.user_id = $1
                """,
                user_id,
            )
            if row is None:
                return None
            score = float(row["score"])
            rank = await conn.fetchval(
                "SELECT COUNT(*) + 1 FROM lb_scores WHERE score > $1", score,
            )
            return {
                "user_id": row["user_id"],
                "rank": int(rank),
                "score": score,
                "name": row["name"],
                "avatar": row["avatar"],
            }

    async def reset(self) -> int:
        async with self.pool.acquire() as conn:
            count = await conn.fetchval("SELECT COUNT(*) FROM lb_scores")
            await conn.execute("TRUNCATE lb_scores, lb_users CASCADE")
            return int(count)