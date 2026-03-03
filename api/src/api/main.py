import asyncio
import os

from fastapi import FastAPI, WebSocket
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
async def dashboard_summary() -> dict:
    return await repo.get_summary()


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = await repo.get_summary()
            await ws.send_json(payload)
            await asyncio.sleep(refresh_interval)
    except Exception:
        await ws.close()
