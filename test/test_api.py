"""
tests/test_api.py
Integration test cho 3 API endpoint.
Dùng httpx.AsyncClient với app trực tiếp (không cần server đang chạy).

Chạy: pytest tests/test_api.py -v
"""

import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from app.main import app


# ─── CLIENT FIXTURE ────────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def client():
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as ac:
        yield ac


# ─── POST /leaderboard/score ──────────────────────────────────────────────────

@pytest.mark.asyncio
class TestUpdateScore:

    async def test_valid_update(self, client):
        res = await client.post("/leaderboard/score", json={
            "user_id": "test_api_user",
            "score": 100,
            "name": "Test User",
            "avatar": "test.png",
        })
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "test_api_user"
        assert data["new_total_score"] >= 100
        assert "rank" in data
        assert "thanh cong" in data["message"].lower()  # FIX: đổi từ "Thành công"

    async def test_score_zero_rejected(self, client):
        res = await client.post("/leaderboard/score", json={
            "user_id": "user_x",
            "score": 0,
        })
        assert res.status_code == 422

    async def test_score_negative_rejected(self, client):
        res = await client.post("/leaderboard/score", json={
            "user_id": "user_x",
            "score": -50,
        })
        assert res.status_code == 422

    async def test_missing_score_rejected(self, client):
        res = await client.post("/leaderboard/score", json={"user_id": "user_x"})
        assert res.status_code == 422

    async def test_empty_user_id_rejected(self, client):
        res = await client.post("/leaderboard/score", json={
            "user_id": "",
            "score": 100,
        })
        assert res.status_code == 422

    async def test_optional_name_avatar(self, client):
        """Không cần name/avatar vẫn OK."""
        res = await client.post("/leaderboard/score", json={
            "user_id": "bare_user",
            "score": 50,
        })
        assert res.status_code == 200


# ─── GET /leaderboard/top ─────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestGetTop:

    async def test_top_default(self, client):
        res = await client.get("/leaderboard/top")
        assert res.status_code == 200
        data = res.json()
        assert "leaderboard" in data
        assert "total_users" in data
        assert "top_n" in data

    async def test_top_custom_n(self, client):
        res = await client.get("/leaderboard/top?n=3")
        assert res.status_code == 200
        assert res.json()["top_n"] <= 3

    async def test_top_n_too_large_rejected(self, client):
        res = await client.get("/leaderboard/top?n=200")
        assert res.status_code == 422

    async def test_top_n_zero_rejected(self, client):
        res = await client.get("/leaderboard/top?n=0")
        assert res.status_code == 422

    async def test_leaderboard_sorted_descending(self, client):
        # Insert 2 user với score biết trước
        await client.post("/leaderboard/score", json={"user_id": "sort_high", "score": 9999})
        await client.post("/leaderboard/score", json={"user_id": "sort_low", "score": 1})

        res = await client.get("/leaderboard/top?n=100")
        lb = res.json()["leaderboard"]
        scores = [e["score"] for e in lb]
        assert scores == sorted(scores, reverse=True), "Leaderboard phải giảm dần"


# ─── GET /leaderboard/rank/{user_id} ─────────────────────────────────────────

@pytest.mark.asyncio
class TestGetRank:

    async def test_rank_existing_user(self, client):
        # Tạo user trước
        await client.post("/leaderboard/score", json={
            "user_id": "rank_test_user",
            "score": 500,
        })
        res = await client.get("/leaderboard/rank/rank_test_user")
        assert res.status_code == 200
        data = res.json()
        assert data["user_id"] == "rank_test_user"
        assert data["rank"] >= 1
        assert data["score"] >= 500

    async def test_rank_nonexistent_user(self, client):
        res = await client.get("/leaderboard/rank/ghost_user_xyz_99999")
        assert res.status_code == 404

    async def test_rank_response_has_all_fields(self, client):
        await client.post("/leaderboard/score", json={
            "user_id": "field_check_user",
            "score": 123,
            "name": "Field Check",
            "avatar": "fc.png",
        })
        res = await client.get("/leaderboard/rank/field_check_user")
        data = res.json()
        for field in ["user_id", "rank", "score", "name", "avatar"]:
            assert field in data, f"Missing field: {field}"


# ─── HEALTH CHECK ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
class TestHealth:

    async def test_health_endpoint(self, client):
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert "status" in data
        assert "redis" in data

    async def test_root_endpoint(self, client):
        res = await client.get("/")
        assert res.status_code == 200
        assert "docs" in res.json()