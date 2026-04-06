import asyncio
import json
import redis.asyncio as aioredis
from fastapi import WebSocket
from app.config import settings

PUBSUB_CHANNEL = "leaderboard:updates"


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, data: dict) -> None:
        message = json.dumps(data, ensure_ascii=False)
        dead = []
        for ws in self.active_connections:
            try:
                await ws.send_text(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = ConnectionManager()


async def publish_update(redis_client: aioredis.Redis, payload: dict) -> None:
    await redis_client.publish(PUBSUB_CHANNEL, json.dumps(payload, ensure_ascii=False))


async def redis_pubsub_listener() -> None:
    client = aioredis.from_url(
        settings.redis_url,
        db=settings.redis_db,
        decode_responses=True,
    )
    pubsub = client.pubsub()
    await pubsub.subscribe(PUBSUB_CHANNEL)
    try:
        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                await manager.broadcast(data)
            except Exception:
                continue
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(PUBSUB_CHANNEL)
        await client.aclose()