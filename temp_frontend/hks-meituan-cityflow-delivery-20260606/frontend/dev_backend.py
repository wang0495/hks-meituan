"""Development backend launcher for the standalone CityFlow frontend.

This keeps the production repository untouched while exposing the real
CityFlow V2 route, POI, and dialogue routers for local frontend integration.
It intentionally skips the full app lifespan that requires Redis-backed
queues and sessions.
"""

from __future__ import annotations

import sys
import os
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

HERE = Path(__file__).resolve()
ENV_BACKEND_REPO = os.environ.get("CITYFLOW_BACKEND_REPO", "").strip()
BACKEND_CANDIDATES = []
if ENV_BACKEND_REPO:
    BACKEND_CANDIDATES.append(Path(ENV_BACKEND_REPO))
BACKEND_CANDIDATES.extend(
    [
        HERE.parents[1] / "hks-meituan-master",
        HERE.parents[2] / "hks-meituan-master",
        Path.cwd() / "hks-meituan-master",
    ]
)
BACKEND_REPO = next(
    (
        path
        for path in BACKEND_CANDIDATES
        if path.exists()
    ),
    HERE.parents[1] / "hks-meituan-master",
)
if str(BACKEND_REPO) not in sys.path:
    sys.path.insert(0, str(BACKEND_REPO))

from backend.routers import health, v2  # noqa: E402
from backend.services.data_service import load_data  # noqa: E402

app = FastAPI(title="CityFlow Frontend Dev Backend", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:8000",
        "http://localhost:8000",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def _startup() -> None:
    load_data()


@app.get("/api/health")
async def api_health() -> dict:
    return {"status": "healthy", "mode": "frontend-dev-real-v2"}


app.include_router(health.router)
app.include_router(v2.router)
