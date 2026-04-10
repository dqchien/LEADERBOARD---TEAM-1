import asyncio
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import leaderboard, websocket
from app.websocket_manager import redis_pubsub_listener
from app.models import HealthResponse
from app.dependencies import set_postgres_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Khởi động Redis pubsub listener
    task = asyncio.create_task(redis_pubsub_listener())

    # Khởi động PostgreSQL pool nếu được cấu hình
    pg_pool = None
    if settings.db_backend == "postgres" or settings.postgres_url:
        try:
            from app.postgres_service import PostgresService
            pg_pool = await PostgresService.create_pool(settings.postgres_url)
            svc = PostgresService(pg_pool)
            await svc.init_schema()          # tạo bảng nếu chưa có
            set_postgres_pool(pg_pool)
            print(f"[DB] PostgreSQL connected: {settings.postgres_url}")
        except Exception as e:
            print(f"[DB] PostgreSQL unavailable: {e} — fallback to Redis")

    yield

    # Cleanup
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    if pg_pool:
        await pg_pool.close()


app = FastAPI(
    title="Real-time Leaderboard API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(leaderboard.router)
app.include_router(websocket.router)


@app.get("/", tags=["System"])
async def root():
    import app.dependencies as deps
    return {
        "message": "Leaderboard API dang chay",
        "current_backend": deps.current_backend,
        "docs": "http://localhost:8000/docs",
        "websocket": "ws://localhost:8000/ws/leaderboard",
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    try:
        client = aioredis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        await client.aclose()
        redis_status = "connected"
    except Exception as e:
        redis_status = f"error: {str(e)}"
    return HealthResponse(
        status="ok" if redis_status == "connected" else "degraded",
        redis=redis_status,
        message="OK" if redis_status == "connected" else "Redis unavailable",
    )
