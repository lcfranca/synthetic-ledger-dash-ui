import asyncio
import os

from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from api.repository import DashboardRepository

app = FastAPI(title="synthetic-ledger-api", version="0.1.0")
repo = DashboardRepository()
refresh_interval = int(os.getenv("API_REFRESH_INTERVAL_MS", "1000")) / 1000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/api/v1/dashboard/summary")
async def dashboard_summary(as_of: str | None = Query(default=None)) -> dict:
    summary = await repo.get_summary(as_of=as_of)
    summary["entries"] = await repo.get_recent_entries(limit=30, as_of=as_of)
    return summary


@app.get("/api/v1/dashboard/entries")
async def dashboard_entries(limit: int = Query(default=50, ge=1, le=500), as_of: str | None = Query(default=None)) -> dict:
    entries = await repo.get_recent_entries(limit=limit, as_of=as_of)
    return {"entries": entries, "count": len(entries), "as_of": as_of}


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = await repo.get_summary()
            payload["entries"] = await repo.get_recent_entries(limit=30)
            await ws.send_json(payload)
            await asyncio.sleep(refresh_interval)
    except Exception:
        await ws.close()
