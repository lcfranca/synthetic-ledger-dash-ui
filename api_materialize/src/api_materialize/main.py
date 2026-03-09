import os

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api_materialize.repository import DashboardRepository, MaterializeQueryError

app = FastAPI(title="synthetic-ledger-api-materialize", version="0.1.0")
repo = DashboardRepository()
refresh_interval = int(os.getenv("API_REFRESH_INTERVAL_MS", "1000")) / 1000

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def repo_filters(
    *,
    product_name: str | None = None,
    product_category: str | None = None,
    supplier_name: str | None = None,
    event_type: str | None = None,
    entry_category: str | None = None,
    account_code: str | None = None,
    warehouse_id: str | None = None,
    entry_side: str | None = None,
    ontology_source: str | None = None,
    channel: str | None = None,
    customer_name: str | None = None,
    customer_cpf: str | None = None,
    customer_email: str | None = None,
    customer_segment: str | None = None,
    sale_id: str | None = None,
    order_id: str | None = None,
    order_status: str | None = None,
    payment_method: str | None = None,
) -> dict[str, str | None]:
    return {
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
        "customer_name": customer_name,
        "customer_cpf": customer_cpf,
        "customer_email": customer_email,
        "customer_segment": customer_segment,
        "sale_id": sale_id,
        "order_id": order_id,
        "order_status": order_status,
        "payment_method": payment_method,
    }


@app.exception_handler(MaterializeQueryError)
async def materialize_query_error_handler(_, exc: MaterializeQueryError):
    return JSONResponse(status_code=503, content={"backend": "materialize", "error": str(exc)})


@app.get("/health")
async def health() -> dict:
    try:
        query_layer = await repo.get_query_layer_metrics()
    except MaterializeQueryError as exc:
        return {"status": "warming_up", "backend": "materialize", "query_layer_error": str(exc)}
    return {"status": "ok", "backend": "materialize", "query_layer": query_layer, "refresh_interval_seconds": refresh_interval}


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
    customer_name: str | None = Query(default=None),
    customer_cpf: str | None = Query(default=None),
    customer_email: str | None = Query(default=None),
    customer_segment: str | None = Query(default=None),
    sale_id: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    order_status: str | None = Query(default=None),
    payment_method: str | None = Query(default=None),
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
        "customer_name": customer_name,
        "customer_cpf": customer_cpf,
        "customer_email": customer_email,
        "customer_segment": customer_segment,
        "sale_id": sale_id,
        "order_id": order_id,
        "order_status": order_status,
        "payment_method": payment_method,
    }
    backend_filters = repo_filters(
        product_name=product_name,
        product_category=product_category,
        supplier_name=supplier_name,
        event_type=event_type,
        entry_category=entry_category,
        account_code=account_code,
        warehouse_id=warehouse_id,
        entry_side=entry_side,
        ontology_source=ontology_source,
        channel=channel,
        customer_name=customer_name,
        customer_cpf=customer_cpf,
        customer_email=customer_email,
        customer_segment=customer_segment,
        sale_id=sale_id,
        order_id=order_id,
        order_status=order_status,
        payment_method=payment_method,
    )
    summary = await repo.get_summary(as_of=as_of, start_at=start_at, end_at=end_at, filters=backend_filters)
    summary["entries"] = await repo.get_recent_entries(limit=30, as_of=as_of, start_at=start_at, end_at=end_at, filters=backend_filters)
    summary["filters"] = filters
    summary["backend"] = "materialize"
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
    customer_name: str | None = Query(default=None),
    customer_cpf: str | None = Query(default=None),
    customer_email: str | None = Query(default=None),
    customer_segment: str | None = Query(default=None),
    sale_id: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    order_status: str | None = Query(default=None),
    payment_method: str | None = Query(default=None),
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
        "customer_name": customer_name,
        "customer_cpf": customer_cpf,
        "customer_email": customer_email,
        "customer_segment": customer_segment,
        "sale_id": sale_id,
        "order_id": order_id,
        "order_status": order_status,
        "payment_method": payment_method,
    }
    entries = await repo.get_recent_entries(limit=limit, as_of=as_of, start_at=start_at, end_at=end_at, filters=filters)
    return {"entries": entries, "count": len(entries), "as_of": as_of, "filters": filters, "backend": "materialize"}


@app.get("/api/v1/dashboard/filter-options")
async def dashboard_filter_options() -> dict:
    return await repo.get_filter_options()


@app.get("/api/v1/dashboard/filter-search")
async def dashboard_filter_search(
    field: str = Query(...),
    query: str = Query(..., min_length=1),
    limit: int = Query(default=20, ge=1, le=50),
) -> dict:
    matches = await repo.search_filter_values(field=field, query=query, limit=limit)
    return {"field": field, "query": query, "matches": matches, "count": len(matches), "backend": "materialize"}


@app.get("/api/v1/master-data/overview")
async def master_data_overview() -> dict:
    return await repo.get_master_data_overview()


@app.get("/api/v1/dashboard/accounts-catalog")
async def dashboard_accounts_catalog() -> dict:
    rows = await repo.get_account_catalog()
    return {"accounts": rows, "count": len(rows), "backend": "materialize"}


@app.get("/api/v1/dashboard/products-catalog")
async def dashboard_products_catalog() -> dict:
    rows = await repo.get_product_catalog()
    return {"products": rows, "count": len(rows), "backend": "materialize"}


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
    customer_name: str | None = Query(default=None),
    customer_cpf: str | None = Query(default=None),
    customer_email: str | None = Query(default=None),
    customer_segment: str | None = Query(default=None),
    sale_id: str | None = Query(default=None),
    order_id: str | None = Query(default=None),
    order_status: str | None = Query(default=None),
    payment_method: str | None = Query(default=None),
) -> dict:
    filters = repo_filters(
        product_name=product_name,
        product_category=product_category,
        supplier_name=supplier_name,
        event_type=event_type,
        entry_category=entry_category,
        account_code=account_code,
        warehouse_id=warehouse_id,
        entry_side=entry_side,
        ontology_source=ontology_source,
        channel=channel,
        customer_name=customer_name,
        customer_cpf=customer_cpf,
        customer_email=customer_email,
        customer_segment=customer_segment,
        sale_id=sale_id,
        order_id=order_id,
        order_status=order_status,
        payment_method=payment_method,
    )
    payload = await repo.get_workspace_snapshot(as_of=as_of, start_at=start_at, end_at=end_at, filters=filters)
    payload["backend"] = "materialize"
    return payload