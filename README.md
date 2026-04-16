# Real-time Leaderboard

A real-time leaderboard system built with FastAPI, Redis, PostgreSQL, and WebSocket.

It provides REST endpoints for score updates, a WebSocket channel for live push notifications, and a static frontend that reflects rank changes instantly without page reload. Supports switching between Redis and PostgreSQL as the storage backend at runtime.

## Features

- REST API to update scores and query rankings
- **Dual backend support**: switch between Redis and PostgreSQL without restarting the server
- Redis Sorted Set (ZSET) for automatic score ordering and O(log N) rank lookup
- Redis Hash for user metadata (name, avatar)
- Atomic score update + rank fetch via Lua script (no race conditions)
- PostgreSQL with asyncpg for persistent, disk-backed storage
- Redis Pub/Sub + WebSocket to push updates to all connected clients in real-time
- FLIP animation for smooth real-time rank reordering in the frontend
- Pinned "Your Rank" bar that animates on rank change
- Simulate button that fires thousands of score updates to demo performance
- Backend switcher UI in the header — no terminal needed to switch

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
LEADERBOARD_KEY=leaderboard

POSTGRES_URL=postgresql://postgres:yourpassword@localhost:5432/leaderboard
DB_BACKEND=redis

APP_HOST=0.0.0.0
APP_PORT=8000
```

**4. (PostgreSQL only) Create the database in pgAdmin or psql:**
```sql
CREATE DATABASE leaderboard;
```
Tables (`lb_users`, `lb_scores`) are created automatically on first startup.

**5. Run the FastAPI app (Terminal 1):**
```bash
uvicorn app.main:app --reload
```

**6. Serve the frontend (Terminal 2):**
```bash
cd frontend
python -m http.server 3000
```

Open the demo at `http://localhost:3000`  
Swagger UI available at `http://localhost:8000/docs`

## Switching backend

### Via UI (recommended)
Click the **⚡ Redis** or **🐘 PostgreSQL** toggle in the page header.  
The active backend is also shown in the stats bar at all times.

### Via terminal
```bash
# Switch to PostgreSQL
curl -X POST "http://localhost:8000/leaderboard/switch-backend?target=postgres"

# Switch back to Redis
curl -X POST "http://localhost:8000/leaderboard/switch-backend?target=redis"

# Check current backend
curl "http://localhost:8000/leaderboard/current-backend"
```

### Via .env (persistent across restarts)
Set `DB_BACKEND=postgres` or `DB_BACKEND=redis` in `.env`, then restart the server.

> **Note:** The switch is live but not persisted — restarting the server resets to the value in `.env`.

## Environment variables

| Variable | Description | Default |
|----------|-------------|---------|
| `REDIS_URL` | Redis connection string | `redis://127.0.0.1:6379` |
| `REDIS_DB` | Redis database index | `0` |
| `LEADERBOARD_KEY` | Redis key for the leaderboard ZSET | `leaderboard` |
| `POSTGRES_URL` | PostgreSQL connection string | `postgresql://postgres@localhost:5432/leaderboard` |
| `DB_BACKEND` | Active backend on startup: `redis` or `postgres` | `redis` |
| `APP_HOST` | Host to bind the server | `0.0.0.0` |
| `APP_PORT` | Port to run the server on | `8000` |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/leaderboard/score` | Add points to a user |
| `GET` | `/leaderboard/top?n=10` | Get top N users |
| `GET` | `/leaderboard/rank/{user_id}` | Get rank of a specific user |
| `DELETE` | `/leaderboard/reset` | Clear all leaderboard data |
| `POST` | `/leaderboard/switch-backend?target=redis\|postgres` | Switch storage backend live |
| `GET` | `/leaderboard/current-backend` | Check which backend is active |
| `GET` | `/health` | Server + Redis health check |
| `WS` | `/ws/leaderboard` | WebSocket stream for live updates |

## Project layout

```
leaderboard/
├── app/
│   ├── main.py              # FastAPI app, CORS, lifespan, Postgres pool init
│   ├── config.py            # Settings from .env (Redis, Postgres, backend switch)
│   ├── repository.py        # Abstract base class defining the storage interface
│   ├── redis_service.py     # Redis implementation (ZSET, HASH, Lua script)
│   ├── postgres_service.py  # PostgreSQL implementation (asyncpg, auto schema init)
│   ├── dependencies.py      # Injects correct service based on current_backend
│   ├── models.py            # Pydantic request/response schemas
│   ├── websocket_manager.py # ConnectionManager + Redis Pub/Sub listener
│   └── routers/
│       ├── leaderboard.py   # REST endpoints + switch-backend endpoint
│       └── websocket.py     # WebSocket endpoint
├── frontend/
│   ├── index.html           # Layout + backend switcher toggle
│   ├── style.css            # Dark theme, FLIP animation, switcher styles
│   └── app.js               # WebSocket client, FLIP reorder, backend switch UI
├── scripts/
│   ├── seed_data.py         # Seed users into Redis
│   └── simulate_score.py    # Async bulk score simulation
├── tests/
│   ├── test_api.py
│   └── test_redis_service.py
├── main.py                  # Entry point (runs uvicorn)
├── requirements.txt
├── .env
├── .env.example
└── README.md
```

## Testing

```bash
pytest tests/ -v
```

## Git / .env hygiene

`.env` and virtual environment directories are intentionally excluded from version control. See `.gitignore`.
