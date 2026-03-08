import asyncio
import json
import os
import uuid
from dataclasses import dataclass
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from confluent_kafka import Consumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        if " " in normalized and "+" not in normalized:
            try:
                return datetime.fromisoformat(normalized.replace(" ", "T") + "+00:00")
            except ValueError:
                return None
    return None


def normalized_filter_value(value: Any) -> str:
    return str(value or "").strip().lower()


def parse_filters(params: Any) -> dict[str, str]:
    supported = {
        "as_of",
        "start_at",
        "end_at",
        "product_name",
        "product_category",
        "supplier_name",
        "event_type",
        "entry_category",
        "account_code",
        "warehouse_id",
        "entry_side",
        "ontology_source",
        "channel",
        "customer_name",
        "customer_cpf",
        "customer_email",
        "customer_segment",
        "sale_id",
        "order_id",
        "order_status",
        "payment_method",
    }
    filters: dict[str, str] = {}
    for name in supported:
        value = params.get(name)
        if value:
            filters[name] = str(value)
    return filters


def entry_matches_filters(entry: dict[str, Any], filters: dict[str, str]) -> bool:
    field_map = {
        "product_name": "product_name",
        "product_category": "product_category",
        "supplier_name": "supplier_name",
        "event_type": "ontology_event_type",
        "entry_category": "entry_category",
        "account_code": "account_code",
        "warehouse_id": "warehouse_id",
        "entry_side": "entry_side",
        "ontology_source": "ontology_source",
        "channel": "channel_name",
        "customer_name": "customer_name",
        "customer_cpf": "customer_cpf",
        "customer_email": "customer_email",
        "customer_segment": "customer_segment",
        "sale_id": "sale_id",
        "order_id": "order_id",
        "order_status": "order_status",
        "payment_method": "payment_method",
    }

    occurred_at = parse_timestamp(entry.get("occurred_at") or entry.get("ingested_at"))
    if filters.get("start_at"):
        start_at = parse_timestamp(filters.get("start_at"))
        if start_at and occurred_at and occurred_at < start_at:
            return False
    upper_bound_raw = filters.get("end_at") or filters.get("as_of")
    if upper_bound_raw:
        upper_bound = parse_timestamp(upper_bound_raw)
        if upper_bound and occurred_at and occurred_at > upper_bound:
            return False

    for filter_name, entry_field in field_map.items():
        filter_value = normalized_filter_value(filters.get(filter_name))
        if filter_value and normalized_filter_value(entry.get(entry_field)) != filter_value:
            return False
    return True


@dataclass
class Subscription:
    websocket: WebSocket
    backend: str
    filters: dict[str, str]


def parse_backends() -> list[str]:
    configured = os.getenv("ACTIVE_STACKS", "clickhouse,druid,pinot")
    ordered = ["clickhouse", "druid", "pinot"]
    enabled = {item.strip() for item in configured.split(",") if item.strip()}
    return [backend for backend in ordered if backend in enabled]


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[str, Subscription]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket, backend: str, filters: dict[str, str]) -> str:
        connection_id = str(uuid.uuid4())
        async with self._lock:
            self._connections[backend][connection_id] = Subscription(websocket=websocket, backend=backend, filters=filters)
        return connection_id

    async def disconnect(self, backend: str, connection_id: str) -> None:
        async with self._lock:
            self._connections[backend].pop(connection_id, None)

    async def has_backend_subscribers(self, backend: str) -> bool:
        async with self._lock:
            return bool(self._connections.get(backend))

    async def snapshot_counts(self) -> dict[str, int]:
        async with self._lock:
            return {backend: len(connections) for backend, connections in self._connections.items()}

    async def subscription(self, backend: str, connection_id: str) -> Subscription | None:
        async with self._lock:
            return self._connections.get(backend, {}).get(connection_id)

    async def subscriptions(self, backend: str) -> list[tuple[str, Subscription]]:
        async with self._lock:
            return list(self._connections.get(backend, {}).items())

    async def broadcast(self, backend: str, message: dict[str, Any], *, matcher: Any | None = None) -> None:
        targets = await self.subscriptions(backend)

        stale_connection_ids: list[str] = []
        for connection_id, subscription in targets:
            if matcher is not None and not matcher(subscription):
                continue
            try:
                await subscription.websocket.send_json(message)
            except Exception:
                stale_connection_ids.append(connection_id)

        if not stale_connection_ids:
            return

        async with self._lock:
            for connection_id in stale_connection_ids:
                self._connections.get(backend, {}).pop(connection_id, None)


class RealtimeGateway:
    def __init__(self) -> None:
        self.topic = os.getenv("LEDGER_ENTRIES_KAFKA_TOPIC", "ledger-entries-v1")
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
        self.group_id = os.getenv("REALTIME_GATEWAY_GROUP_ID", "realtime-gateway-v1")
        self.offset_reset = os.getenv("REALTIME_GATEWAY_AUTO_OFFSET_RESET", "latest")
        self.active_backends = parse_backends()
        self.backend_urls = {
            "clickhouse": os.getenv("REALTIME_GATEWAY_CLICKHOUSE_API_URL", "http://api:8080"),
            "druid": os.getenv("REALTIME_GATEWAY_DRUID_API_URL", "http://api-druid:8080"),
            "pinot": os.getenv("REALTIME_GATEWAY_PINOT_API_URL", "http://api-pinot:8080"),
        }
        self.manager = ConnectionManager()
        self.client = httpx.AsyncClient(timeout=8.0)
        self.consumer = Consumer(
            {
                "bootstrap.servers": self.bootstrap_servers,
                "group.id": self.group_id,
                "auto.offset.reset": self.offset_reset,
                "enable.auto.commit": False,
            }
        )
        self.consumer.subscribe([self.topic])
        self.consumer_task: asyncio.Task[Any] | None = None
        self.state: dict[str, Any] = {
            "state": "idle",
            "topic": self.topic,
            "delivery_mode": "push-only",
            "messages_processed": 0,
            "last_event_id": None,
            "last_offsets": None,
            "last_error": None,
        }

    async def close(self) -> None:
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()
        await asyncio.to_thread(self.consumer.close)

    async def fetch_workspace(self, backend: str, filters: dict[str, str] | None = None) -> dict[str, Any] | None:
        base_url = self.backend_urls.get(backend)
        if not base_url:
            return None
        try:
            response = await self.client.get(f"{base_url}/api/v1/dashboard/workspace", params=filters or None)
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                payload["backend"] = backend
                return payload
        except Exception as exc:
            self.state["last_error"] = f"workspace:{backend}:{exc}"
        return None

    async def send_snapshot(
        self,
        backend: str,
        websocket: WebSocket | None = None,
        filters: dict[str, str] | None = None,
        connection_id: str | None = None,
    ) -> None:
        payload = await self.fetch_workspace(backend, filters)
        if payload is None:
            return
        message = {
            "event_id": f"dashboard-{backend}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            "event_type": "dashboard.snapshot",
            "version": "1.0.0",
            "backend": backend,
            "ts": now_iso(),
            "payload": payload,
        }
        if websocket is not None:
            await websocket.send_json(message)
            return
        if connection_id is not None:
            subscription = await self.manager.subscription(backend, connection_id)
            if subscription is None:
                return
            await subscription.websocket.send_json(message)
            return
        await self.manager.broadcast(backend, message)

    async def consume(self) -> None:
        while True:
            try:
                kafka_message = await asyncio.to_thread(self.consumer.poll, 1.0)
                if kafka_message is None:
                    self.state["state"] = "idle"
                    continue

                if kafka_message.error():
                    self.state["state"] = "error"
                    self.state["last_error"] = str(kafka_message.error())
                    await asyncio.sleep(1)
                    continue

                entry = json.loads(kafka_message.value().decode("utf-8"))
                self.state["state"] = "running"
                self.state["messages_processed"] = int(self.state.get("messages_processed", 0)) + 1
                self.state["last_event_id"] = entry.get("event_id")
                self.state["last_error"] = None
                self.state["last_offsets"] = {
                    "topic": kafka_message.topic(),
                    "partition": kafka_message.partition(),
                    "offset": kafka_message.offset(),
                }

                for backend in self.active_backends:
                    subscriptions = await self.manager.subscriptions(backend)
                    if not subscriptions:
                        continue
                    outbound_message = {
                        "event_id": entry.get("entry_id") or entry.get("event_id") or str(uuid.uuid4()),
                        "event_type": "entry.created",
                        "version": "1.0.0",
                        "backend": backend,
                        "ts": str(entry.get("ingested_at") or entry.get("occurred_at") or now_iso()),
                        "payload": entry,
                    }
                    matched_connection_ids: list[str] = []
                    for connection_id, subscription in subscriptions:
                        if entry_matches_filters(entry, subscription.filters):
                            matched_connection_ids.append(connection_id)
                    if not matched_connection_ids:
                        continue
                    await self.manager.broadcast(
                        backend,
                        outbound_message,
                        matcher=lambda subscription: entry_matches_filters(entry, subscription.filters),
                    )
                await asyncio.to_thread(self.consumer.commit, message=kafka_message, asynchronous=False)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.state["state"] = "error"
                self.state["last_error"] = str(exc)
                await asyncio.sleep(1)


app = FastAPI(title="synthetic-ledger-realtime-gateway", version="0.1.0")
gateway = RealtimeGateway()


@app.on_event("startup")
async def on_startup() -> None:
    gateway.consumer_task = asyncio.create_task(gateway.consume())


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await gateway.close()


@app.get("/health")
async def health() -> dict[str, Any]:
    return {
        "status": "ok",
        "active_backends": gateway.active_backends,
        "connections": await gateway.manager.snapshot_counts(),
        "consumer": gateway.state,
    }


@app.websocket("/ws/dashboard")
async def ws_dashboard(websocket: WebSocket) -> None:
    requested_backend = (websocket.query_params.get("backend") or "").strip().lower()
    if requested_backend not in gateway.active_backends:
        await websocket.close(code=1008)
        return

    await websocket.accept()
    filters = parse_filters(websocket.query_params)
    try:
        connection_id = await gateway.manager.register(websocket, requested_backend, filters)
        await gateway.send_snapshot(requested_backend, websocket, filters)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        if 'connection_id' in locals():
            await gateway.manager.disconnect(requested_backend, connection_id)