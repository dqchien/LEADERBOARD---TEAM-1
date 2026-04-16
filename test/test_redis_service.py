"""
tests/test_redis_service.py
Unit test cho RedisService — dùng Redis thật (cần Redis đang chạy).
Test các case từ notebook: score hợp lệ, score âm, user không tồn tại, data bẩn.

Chạy: pytest tests/test_redis_service.py -v
"""

import pytest
import pytest_asyncio
import redis.asyncio as aioredis
from app.redis_service import RedisService, validate_score, validate_user_id
from app.config import settings

TEST_LEADERBOARD = "leaderboard:test"   # dùng key riêng để không ảnh hưởng data thật


# ─── FIXTURE ──────────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def redis_client():
    """Tạo Redis client cho mỗi test, dọn dẹp sau khi xong."""
    client = aioredis.from_url(settings.redis_url, db=15, decode_responses=True)
    yield client
    # Cleanup: xoá toàn bộ key test
    keys = await client.keys("*")
    if keys:
        await client.delete(*keys)
    await client.aclose()


@pytest_asyncio.fixture
async def svc(redis_client):
    """RedisService dùng test leaderboard key."""
    service = RedisService(redis_client)
    # Override leaderboard key để dùng key test
    import app.redis_service as rs
    rs.LEADERBOARD_KEY = TEST_LEADERBOARD
    yield service
    rs.LEADERBOARD_KEY = settings.leaderboard_key  # restore


# ─── VALIDATE SCORE (từ notebook) ─────────────────────────────────────────────

class TestValidateScore:
    def test_valid_score(self):
        validate_score(100)      # int
        validate_score(50.5)     # float
        validate_score(0.01)     # nhỏ nhưng > 0

    def test_score_none_raises(self):
        with pytest.raises(ValueError, match="None"):
            validate_score(None)

    def test_score_zero_raises(self):
        with pytest.raises(ValueError, match="> 0"):
            validate_score(0)

    def test_score_negative_raises(self):
        with pytest.raises(ValueError):
            validate_score(-10)

    def test_score_string_raises(self):
        with pytest.raises(TypeError, match="số"):
            validate_score("abc")

    def test_score_string_number_raises(self):
        with pytest.raises(TypeError):
            validate_score("100")


# ─── VALIDATE USER ID ─────────────────────────────────────────────────────────

class TestValidateUserId:
    def test_valid_user_id(self):
        validate_user_id("user_1")
        validate_user_id("abc123")

    def test_empty_raises(self):
        with pytest.raises(ValueError):
            validate_user_id("")

    def test_none_raises(self):
        with pytest.raises(ValueError):
            validate_user_id(None)

    def test_not_string_raises(self):
        with pytest.raises(ValueError):
            validate_user_id(123)


# ─── REDIS SERVICE ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestRedisService:

    async def test_update_score_new_user(self, svc):
        result = await svc.update_score("user_test_1", 100)
        assert result["user_id"] == "user_test_1"
        assert result["new_total_score"] == 100.0
        assert result["rank"] == 1

    async def test_update_score_accumulates(self, svc):
        await svc.update_score("user_test_2", 50)
        result = await svc.update_score("user_test_2", 30)
        assert result["new_total_score"] == 80.0

    async def test_update_score_invalid_score(self, svc):
        with pytest.raises(ValueError):
            await svc.update_score("user_1", -5)

    async def test_get_top_n(self, svc):
        await svc.update_score("u_a", 300)
        await svc.update_score("u_b", 100)
        await svc.update_score("u_c", 200)

        top = await svc.get_top_n(2)
        assert len(top) == 2
        assert top[0]["user_id"] == "u_a"
        assert top[0]["rank"] == 1
        assert top[1]["user_id"] == "u_c"

    async def test_get_rank_correct_order(self, svc):
        await svc.update_score("rank_a", 500)
        await svc.update_score("rank_b", 300)
        await svc.update_score("rank_c", 100)

        assert await svc.get_rank("rank_a") == 1
        assert await svc.get_rank("rank_b") == 2
        assert await svc.get_rank("rank_c") == 3

    async def test_get_rank_nonexistent_user(self, svc):
        rank = await svc.get_rank("ghost_user_9999")
        assert rank is None

    async def test_create_and_get_user(self, svc):
        await svc.create_user("user_meta", "Test User", "test.png")
        data = await svc.get_user("user_meta")
        assert data["name"] == "Test User"
        assert data["avatar"] == "test.png"

    async def test_get_user_not_exists(self, svc):
        data = await svc.get_user("totally_new_user_xyz")
        assert data == {}

    async def test_get_rank_info_full(self, svc):
        await svc.update_score("full_user", 777)
        await svc.create_user("full_user", "Full Name", "full.png")

        info = await svc.get_rank_info("full_user")
        assert info is not None
        assert info["score"] == 777.0
        assert info["name"] == "Full Name"
        assert info["avatar"] == "full.png"

    async def test_get_rank_info_not_in_leaderboard(self, svc):
        result = await svc.get_rank_info("nobody_xyz")
        assert result is None

    async def test_total_users(self, svc):
        await svc.update_score("count_1", 10)
        await svc.update_score("count_2", 20)
        total = await svc.get_total_users()
        assert total >= 2