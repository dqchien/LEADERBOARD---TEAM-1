"""
scripts/seed_data.py
Chuyển từ insert_users() trong Jupyter notebook sang script độc lập.
Insert N user với score ngẫu nhiên vào Redis.

Chạy: python scripts/seed_data.py
       python scripts/seed_data.py --users 10000
"""

import sys
import os
import time
import random
import argparse

# Thêm root vào sys.path để import app.*
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import redis

from app.config import settings

# ─── CONFIG ───────────────────────────────────────────────────────────────────

DEFAULT_NUM_USERS = 5000
LEADERBOARD_KEY = settings.leaderboard_key
SCORE_MIN = 0
SCORE_MAX = 2000
NAMES = ["An", "Bình", "Chi", "Dũng", "Em", "Phong", "Giang", "Hoa",
         "Inh", "Khoa", "Lan", "Minh", "Nam", "Oanh", "Phúc"]


# ─── SYNC CLIENT (seed script không cần async) ────────────────────────────────

def get_sync_client() -> redis.Redis:
    return redis.from_url(settings.redis_url, db=settings.redis_db, decode_responses=True)


# ─── SEED ─────────────────────────────────────────────────────────────────────

def clear_leaderboard(r: redis.Redis) -> None:
    """Xoá toàn bộ dữ liệu cũ trước khi seed."""
    existing_keys = r.keys("user:*")
    if existing_keys:
        r.delete(*existing_keys)
    r.delete(LEADERBOARD_KEY)
    print("🗑  Cleared old leaderboard data")


def insert_users(r: redis.Redis, n: int) -> None:
    """
    Insert n user vào Redis.
    Giống insert_users() trong notebook nhưng dùng pipeline để nhanh hơn.
    """
    start = time.time()

    # Dùng pipeline để batch nhiều lệnh → giảm round-trip
    pipe = r.pipeline(transaction=False)

    for i in range(1, n + 1):
        user_id = f"user_{i}"
        score = random.randint(SCORE_MIN, SCORE_MAX)
        name = f"{random.choice(NAMES)}{i}"
        avatar = f"avatar{i}.png"

        # ZINCRBY vào leaderboard
        pipe.zincrby(LEADERBOARD_KEY, score, user_id)

        # HSET metadata (key: user:user_1, user:user_2, ...)
        pipe.hset(f"user:{user_id}", mapping={"name": name, "avatar": avatar})

        # Flush mỗi 500 lệnh để tránh memory spike
        if i % 500 == 0:
            pipe.execute()

    pipe.execute()  # flush còn lại

    elapsed = time.time() - start
    print(f"✅ Inserted {n} users in {elapsed:.2f}s")


def test_top_n(r: redis.Redis, n: int = 10) -> None:
    """Giống test_top_n() trong notebook."""
    start = time.time()
    top = r.zrevrange(LEADERBOARD_KEY, 0, n - 1, withscores=True)
    elapsed = time.time() - start

    print(f"\n🏆 Top {n} users:")
    for rank, (user_id, score) in enumerate(top, start=1):
        user_data = r.hgetall(f"user:{user_id}")
        print(f"  #{rank:>3} {user_id:<12} score={score:.0f}  name={user_data.get('name', '?')}")

    print(f"⏱  Time: {elapsed:.5f}s")


def test_rank(r: redis.Redis, num_users: int) -> None:
    """Giống test_rank() trong notebook."""
    user_id = f"user_{random.randint(1, num_users)}"
    start = time.time()
    rank = r.zrevrank(LEADERBOARD_KEY, user_id)
    elapsed = time.time() - start

    score = r.zscore(LEADERBOARD_KEY, user_id)
    print(f"\n📍 Rank of {user_id}: #{rank + 1}  score={score:.0f}")
    print(f"⏱  Time: {elapsed:.5f}s")


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Seed leaderboard data vào Redis")
    parser.add_argument("--users", type=int, default=DEFAULT_NUM_USERS,
                        help=f"Số user cần insert (default: {DEFAULT_NUM_USERS})")
    parser.add_argument("--clear", action="store_true",
                        help="Xoá dữ liệu cũ trước khi seed")
    args = parser.parse_args()

    r = get_sync_client()

    try:
        r.ping()
        print(f"🔗 Connected to Redis: {settings.redis_url}")
    except Exception as e:
        print(f"❌ Cannot connect to Redis: {e}")
        sys.exit(1)

    if args.clear:
        clear_leaderboard(r)

    insert_users(r, args.users)
    test_top_n(r, 10)
    test_rank(r, args.users)

    total = r.zcard(LEADERBOARD_KEY)
    print(f"\n📊 Total users in leaderboard: {total}")


if __name__ == "__main__":
    main()