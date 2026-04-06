import asyncio
import redis.asyncio as aioredis
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.routers import leaderboard, websocket
from app.websocket_manager import redis_pubsub_listener
from app.models import HealthResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(redis_pubsub_listener())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Real-time Leaderboard API",
    version="1.0.0",
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
    return {
        "message": "Leaderboard API dang chay",
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