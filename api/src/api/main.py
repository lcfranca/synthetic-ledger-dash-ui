import asyncio
import os
from datetime import datetime, timezone

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
    return {"status": "ok", "backend": "clickhouse"}


@app.get("/api/v1/dashboard/summary")
async def dashboard_summary(
    as_of: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    product_category: str | None = Query(default=None),
    supplier_name: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entry_category: str | None = Query(default=None),
    account_code: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    entry_side: str | None = Query(default=None),
    ontology_source: str | None = Query(default=None),
    channel: str | None = Query(default=None),
) -> dict:
    filters = {
        "as_of": as_of,
        "start_at": start_at,
        "end_at": end_at,
        "product_name": product_name,
        "product_category": product_category,
        "supplier_name": supplier_name,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel_name": channel,
    }
    repo_filters = {
        "product_name": product_name,
        "product_category": product_category,
        "supplier_name": supplier_name,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel_name": channel,
    }
    summary = await repo.get_summary(as_of=as_of, start_at=start_at, end_at=end_at, filters=repo_filters)
    summary["entries"] = await repo.get_recent_entries(limit=30, as_of=as_of, start_at=start_at, end_at=end_at, filters=repo_filters)
    summary["filters"] = filters
    summary["backend"] = "clickhouse"
    return summary


@app.get("/api/v1/dashboard/entries")
async def dashboard_entries(
    limit: int = Query(default=50, ge=1, le=500),
    as_of: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    product_category: str | None = Query(default=None),
    supplier_name: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entry_category: str | None = Query(default=None),
    account_code: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    entry_side: str | None = Query(default=None),
    ontology_source: str | None = Query(default=None),
    channel: str | None = Query(default=None),
) -> dict:
    filters = {
        "as_of": as_of,
        "start_at": start_at,
        "end_at": end_at,
        "product_name": product_name,
        "product_category": product_category,
        "supplier_name": supplier_name,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel_name": channel,
    }
    repo_filters = {
        "product_name": product_name,
        "product_category": product_category,
        "supplier_name": supplier_name,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel_name": channel,
    }
    entries = await repo.get_recent_entries(limit=limit, as_of=as_of, start_at=start_at, end_at=end_at, filters=repo_filters)
    return {"entries": entries, "count": len(entries), "as_of": as_of, "filters": filters, "backend": "clickhouse"}


@app.get("/api/v1/dashboard/filter-options")
async def dashboard_filter_options() -> dict:
    return await repo.get_filter_options()


@app.get("/api/v1/master-data/overview")
async def master_data_overview() -> dict:
    return await repo.get_master_data_overview()


@app.get("/api/v1/dashboard/accounts-catalog")
async def dashboard_accounts_catalog() -> dict:
    rows = await repo.get_account_catalog()
    return {"accounts": rows, "count": len(rows), "backend": "clickhouse"}


@app.get("/api/v1/dashboard/products-catalog")
async def dashboard_products_catalog() -> dict:
    rows = await repo.get_product_catalog()
    return {"products": rows, "count": len(rows), "backend": "clickhouse"}


@app.get("/api/v1/dashboard/workspace")
async def dashboard_workspace(
    as_of: str | None = Query(default=None),
    start_at: str | None = Query(default=None),
    end_at: str | None = Query(default=None),
    product_name: str | None = Query(default=None),
    product_category: str | None = Query(default=None),
    supplier_name: str | None = Query(default=None),
    event_type: str | None = Query(default=None),
    entry_category: str | None = Query(default=None),
    account_code: str | None = Query(default=None),
    warehouse_id: str | None = Query(default=None),
    entry_side: str | None = Query(default=None),
    ontology_source: str | None = Query(default=None),
    channel: str | None = Query(default=None),
) -> dict:
    repo_filters = {
        "product_name": product_name,
        "product_category": product_category,
        "supplier_name": supplier_name,
        "ontology_event_type": event_type,
        "entry_category": entry_category,
        "account_code": account_code,
        "warehouse_id": warehouse_id,
        "entry_side": entry_side,
        "ontology_source": ontology_source,
        "channel_name": channel,
    }
    payload = await repo.get_workspace_snapshot(as_of=as_of, start_at=start_at, end_at=end_at, filters=repo_filters)
    payload["backend"] = "clickhouse"
    return payload


@app.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = await repo.get_summary()
            payload["entries"] = await repo.get_recent_entries(limit=30)
            payload["backend"] = "clickhouse"
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


@app.websocket("/ws/dashboard")
async def ws_dashboard(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            payload = await repo.get_workspace_snapshot()
            await ws.send_json(
                {
                    "event_id": f"dashboard-clickhouse-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                    "event_type": "dashboard.snapshot",
                    "version": "1.0.0",
                    "backend": "clickhouse",
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "payload": payload,
                }
            )
            await asyncio.sleep(refresh_interval)
    except WebSocketDisconnect:
        return
    except Exception:
        if ws.application_state != WebSocketState.DISCONNECTED:
            try:
                await ws.close()
            except RuntimeError:
                return
