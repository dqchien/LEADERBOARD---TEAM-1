"""
app/repository.py
─────────────────
Interface chung cho leaderboard backend.
Cả RedisService lẫn PostgresService đều kế thừa class này.
Các route chỉ cần biết LeaderboardRepository, không cần biết backend cụ thể.
"""

from abc import ABC, abstractmethod
from typing import Optional


class LeaderboardRepository(ABC):

    @abstractmethod
    async def update_score(self, user_id: str, score: float) -> dict:
        """Cộng điểm cho user, trả về {user_id, new_total_score, rank}."""
        ...

    @abstractmethod
    async def get_top_n(self, n: int) -> list[dict]:
        """Trả về top N user, mỗi phần tử có rank/user_id/score/name/avatar."""
        ...

    @abstractmethod
    async def get_rank(self, user_id: str) -> Optional[int]:
        """Trả về rank hiện tại của user (1-based), None nếu chưa có điểm."""
        ...

    @abstractmethod
    async def get_score(self, user_id: str) -> Optional[float]:
        """Trả về tổng điểm của user, None nếu chưa có."""
        ...

    @abstractmethod
    async def get_total_users(self) -> int:
        """Tổng số user đang có trong leaderboard."""
        ...

    @abstractmethod
    async def get_user(self, user_id: str) -> dict:
        """Trả về metadata của user: {name, avatar}."""
        ...

    @abstractmethod
    async def create_user(self, user_id: str, name: str, avatar: str) -> None:
        """Tạo hoặc cập nhật metadata user."""
        ...

    @abstractmethod
    async def get_rank_info(self, user_id: str) -> Optional[dict]:
        """Trả về {user_id, rank, score, name, avatar}, None nếu chưa có."""
        ...

    @abstractmethod
    async def reset(self) -> int:
        """Xoá toàn bộ dữ liệu, trả về số user đã xoá."""
        ...