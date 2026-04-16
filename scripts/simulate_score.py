"""
scripts/simulate_score.py
Giả lập hàng nghìn lượt cập nhật điểm liên tục để demo tốc độ Redis in-memory.
Gọi trực tiếp Redis (không qua API) để tối đa throughput.

Chạy: python scripts/simulate_score.py
       python scripts/simulate_score.py --rounds 5000 --users 5000
"""

import sys
import os
import time
import random
import asyncio
import argparse

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import redis.asyncio as aioredis
from app.config import settings

LEADERBOARD_KEY = settings.leaderboard_key


async def simulate(num_rounds: int, num_users: int, concurrency: int) -> None:
    """
    Gửi num_rounds lượt ZINCRBY ngẫu nhiên với concurrency tasks song song.
    In thống kê throughput cuối cùng.
    """
    client = aioredis.from_url(
        settings.redis_url,
        db=settings.redis_db,
        decode_responses=True,
        max_connections=concurrency + 5,
    )

    semaphore = asyncio.Semaphore(concurrency)
    success_count = 0
    errors = 0

    async def one_update():
        nonlocal success_count, errors
        user_id = f"user_{random.randint(1, num_users)}"
        score = random.randint(1, 100)
        async with semaphore:
            try:
                await client.zincrby(LEADERBOARD_KEY, score, user_id)
                success_count += 1
            except Exception:
                errors += 1

    print(f"🚀 Simulating {num_rounds} score updates  |  users={num_users}  |  concurrency={concurrency}")
    start = time.time()

    await asyncio.gather(*[one_update() for _ in range(num_rounds)])

    elapsed = time.time() - start
    rps = success_count / elapsed if elapsed > 0 else 0

    print(f"✅ Done in {elapsed:.2f}s")
    print(f"   Success : {success_count:,}")
    print(f"   Errors  : {errors}")
    print(f"   Throughput: {rps:,.0f} ops/sec")

    await client.aclose()


def main():
    parser = argparse.ArgumentParser(description="Giả lập nạp điểm hàng loạt")
    parser.add_argument("--rounds", type=int, default=2000,
                        help="Số lượt update (default: 2000)")
    parser.add_argument("--users", type=int, default=5000,
                        help="Phạm vi user_id (default: 5000)")
    parser.add_argument("--concurrency", type=int, default=50,
                        help="Số task async đồng thời (default: 50)")
    args = parser.parse_args()

    asyncio.run(simulate(args.rounds, args.users, args.concurrency))


if __name__ == "__main__":
    main()