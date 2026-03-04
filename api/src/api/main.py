import asyncio
import os

from fastapi import FastAPI, Query, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from starlette.websockets import WebSocketDisconnect, WebSocketState

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
async def dashboard_summary(
    as_of: str | None = Query(default=None),
    product_id: str | None = Query(default=None),
    supplier_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entry_category: str | None = Query(default=None),
    account_code: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    entry_side: str | None = Query(default=None),
    ontology_source: str | None = Query(default=None),
    channel: str | None = Query(default=None),
) -> dict:
    filters = {
        "product_id": product_id,
        "supplier_id": supplier_id,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel": channel,
    }
    summary = await repo.get_summary(as_of=as_of, filters=filters)
    summary["entries"] = await repo.get_recent_entries(limit=30, as_of=as_of, filters=filters)
    summary["filters"] = filters
    return summary


@app.get("/api/v1/dashboard/entries")
async def dashboard_entries(
    limit: int = Query(default=50, ge=1, le=500),
    as_of: str | None = Query(default=None),
    product_id: str | None = Query(default=None),
    supplier_id: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entry_category: str | None = Query(default=None),
    account_code: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    entry_side: str | None = Query(default=None),
    ontology_source: str | None = Query(default=None),
    channel: str | None = Query(default=None),
) -> dict:
    filters = {
        "product_id": product_id,
        "supplier_id": supplier_id,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel": channel,
    }
    entries = await repo.get_recent_entries(limit=limit, as_of=as_of, filters=filters)
    return {"entries": entries, "count": len(entries), "as_of": as_of, "filters": filters}


@app.get("/api/v1/dashboard/filter-options")
async def dashboard_filter_options() -> dict:
    return await repo.get_filter_options()


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = await repo.get_summary()
            payload["entries"] = await repo.get_recent_entries(limit=30)
            await ws.send_json(payload)
            await asyncio.sleep(refresh_interval)
    except WebSocketDisconnect:
        return
    except Exception:
        if ws.application_state != WebSocketState.DISCONNECTED:
            try:
                await ws.close()
            except RuntimeError:
                return
