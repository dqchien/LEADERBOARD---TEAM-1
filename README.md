# Real-time leaderboard

A real-time leaderboard system built with FastAPI, Redis, and WebSocket.

It provides REST endpoints for score updates, a WebSocket channel for live push notifications, and a static frontend that reflects rank changes instantly without page reload.

## Features

- REST API to update scores and query rankings
- Redis Sorted Set (ZSET) for automatic score ordering and O(log N) rank lookup
- Redis Hash for user metadata (name, avatar)
- Atomic score update + rank fetch via Lua script (no race conditions)
- Redis Pub/Sub + WebSocket to push updates to all connected clients in real-time
- Pinned "Your Rank" bar that animates on rank change
- Simulate button that fires thousands of score updates to demo Redis in-memory speed

## Quickstart (local)

**1. Create and activate a virtual environment:**
```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
source .venv/bin/activate    # macOS/Linux
```

**2. Install dependencies:**
```bash
pip install -r requirements.txt
```

**3. Provide environment variables in a `.env` file** (copy from `.env.example`):
```env
REDIS_URL=redis://127.0.0.1:6379
REDIS_DB=0
APP_PORT=8000
LEADERBOARD_KEY=leaderboard
```

**4. Seed initial data into Redis:**
```bash
python scripts/seed_data.py --clear
```

**5. Run the FastAPI app (Terminal 1):**
```bash
python main.py
```

**6. Serve the frontend (Terminal 2):**
```bash
cd frontend
python -m http.server 3000
```

Open the demo at `http://localhost:3000`  
Swagger UI available at `http://localhost:8000/docs`

## Environment variables

Keep sensitive values out of source control — use `.env` and `.gitignore`.

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | `redis://127.0.0.1:6379` |
| `REDIS_DB` | Redis database index | `0` |
| `APP_PORT` | Port to run the server on | `8000` |
| `LEADERBOARD_KEY` | Redis key for the leaderboard ZSET | `leaderboard` |

Adjust `app/config.py` for exact variable names and defaults.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/leaderboard/score` | Add points to a user |
| `GET` | `/leaderboard/top?n=10` | Get top N users |
| `GET` | `/leaderboard/rank/{user_id}` | Get rank of a specific user |
| `GET` | `/health` | Server + Redis health check |
| `WS` | `/ws/leaderboard` | WebSocket stream for live updates |

## Project layout

```
leaderboard/
├── app/
│   ├── main.py              # FastAPI app, CORS, lifespan
│   ├── config.py            # Settings from .env
│   ├── dependencies.py      # Redis client & service injection
│   ├── models.py            # Pydantic request/response schemas
│   ├── redis_service.py     # ZSET, HASH, Lua script logic
│   ├── websocket_manager.py # ConnectionManager + Pub/Sub listener
│   └── routers/
│       ├── leaderboard.py   # REST endpoints
│       └── websocket.py     # WebSocket endpoint
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── app.js
├── scripts/
│   ├── seed_data.py         # Seed 5000 users into Redis
│   └── simulate_score.py    # Async bulk score simulation
├── tests/
│   ├── test_api.py
│   └── test_redis_service.py
├── main.py                  # Entry point (runs uvicorn)
├── requirements.txt
├── .env.example
└── README.md
```

## Testing

```bash
pytest tests/ -v
```

## Git / .env hygiene

`.env` and virtual environment directories are intentionally excluded from version control. See `.gitignore`.
