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

from realtime_gateway.projection import seed_runtime_metadata, with_realtime_entry


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


@dataclass
class SnapshotCacheEntry:
    payload: dict[str, Any]
    fetched_at: float


@dataclass
class AuthoritativeProjectionEntry:
    backend: str
    filters: dict[str, str]
    workspace: dict[str, Any]
    runtime: dict[str, Any]
    created_at: str
    last_accessed_at: str
    projection_updates: int = 0
    snapshot_emits: int = 0
    last_event_id: str | None = None
    last_event_ts: str | None = None
    last_event_consumed_at: str | None = None
    last_snapshot_emitted_at: str | None = None
    last_emit_lag_ms: float | None = None
    last_event_age_at_emit_ms: float | None = None


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
        self.snapshot_cache: dict[str, SnapshotCacheEntry] = {}
        self.snapshot_refresh_tasks: dict[str, asyncio.Task[dict[str, Any] | None]] = {}
        self.snapshot_lock = asyncio.Lock()
        self.background_tasks: set[asyncio.Task[Any]] = set()
        authoritative_backends = os.getenv("REALTIME_GATEWAY_AUTHORITATIVE_BACKENDS", "").strip()
        if authoritative_backends:
            self.authoritative_projection_backends = {
                backend.strip()
                for backend in authoritative_backends.split(",")
                if backend.strip()
            }
        else:
            self.authoritative_projection_backends = {
                backend for backend in self.active_backends if backend in {"clickhouse", "druid"}
            }
        self.authoritative_supported_filters = {
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
        self.authoritative_projections: dict[str, AuthoritativeProjectionEntry] = {}
        self.authoritative_lock = asyncio.Lock()
        self.authoritative_broadcast_tasks: dict[str, asyncio.Task[Any]] = {}
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
        for task in list(self.background_tasks):
            task.cancel()
        for task in list(self.snapshot_refresh_tasks.values()):
            task.cancel()
        for task in list(self.authoritative_broadcast_tasks.values()):
            task.cancel()
        if self.consumer_task:
            self.consumer_task.cancel()
            try:
                await self.consumer_task
            except asyncio.CancelledError:
                pass
        await self.client.aclose()
        await asyncio.to_thread(self.consumer.close)

    @staticmethod
    def _projection_cache_key(backend: str, filters: dict[str, str] | None = None) -> str:
        serialized_filters = json.dumps(filters or {}, sort_keys=True, separators=(",", ":"))
        return f"{backend}:{serialized_filters}"

    def _uses_authoritative_projection(self, backend: str, filters: dict[str, str] | None = None) -> bool:
        if backend not in self.authoritative_projection_backends:
            return False
        normalized_filters = filters or {}
        return all(filter_name in self.authoritative_supported_filters for filter_name in normalized_filters)

    @staticmethod
    def _snapshot_cache_key(backend: str, filters: dict[str, str] | None = None) -> str:
        serialized_filters = json.dumps(filters or {}, sort_keys=True, separators=(",", ":"))
        return f"{backend}:{serialized_filters}"

    def _track_background_task(self, task: asyncio.Task[Any]) -> None:
        self.background_tasks.add(task)
        task.add_done_callback(self.background_tasks.discard)

    async def _snapshot_from_cache(self, backend: str, filters: dict[str, str] | None = None) -> dict[str, Any] | None:
        cache_key = self._snapshot_cache_key(backend, filters)
        async with self.snapshot_lock:
            cached = self.snapshot_cache.get(cache_key)
        if not cached:
            return None
        return {**cached.payload}

    async def _store_snapshot(self, backend: str, filters: dict[str, str] | None, payload: dict[str, Any]) -> dict[str, Any]:
        cache_key = self._snapshot_cache_key(backend, filters)
        snapshot_payload = {**payload, "backend": backend}
        async with self.snapshot_lock:
            self.snapshot_cache[cache_key] = SnapshotCacheEntry(payload=snapshot_payload, fetched_at=asyncio.get_running_loop().time())
        return {**snapshot_payload}

    async def _set_authoritative_projection(self, backend: str, filters: dict[str, str] | None, payload: dict[str, Any]) -> dict[str, Any]:
        normalized_filters = dict(filters or {})
        workspace = {**payload, "backend": backend}
        runtime = seed_runtime_metadata(workspace)
        now = now_iso()
        projection_key = self._projection_cache_key(backend, normalized_filters)
        async with self.authoritative_lock:
            self.authoritative_projections[projection_key] = AuthoritativeProjectionEntry(
                backend=backend,
                filters=normalized_filters,
                workspace=workspace,
                runtime=runtime,
                created_at=now,
                last_accessed_at=now,
            )
        await self._store_snapshot(backend, normalized_filters, workspace)
        return {**workspace}

    async def _get_authoritative_projection(self, backend: str, filters: dict[str, str] | None = None) -> dict[str, Any] | None:
        projection_key = self._projection_cache_key(backend, filters)
        async with self.authoritative_lock:
            projection = self.authoritative_projections.get(projection_key)
            if projection is not None:
                projection.last_accessed_at = now_iso()
        if projection is None:
            return None
        return {**projection.workspace}

    async def _apply_authoritative_projection(self, projection_key: str, entry: dict[str, Any], ts: str, consumed_at: str) -> dict[str, Any] | None:
        async with self.authoritative_lock:
            projection = self.authoritative_projections.get(projection_key)
            if projection is None:
                return None
            next_workspace, next_runtime = with_realtime_entry(projection.workspace, entry, projection.backend, ts, projection.runtime)
            if next_workspace is None or next_runtime is None:
                return None
            projection.workspace = next_workspace
            projection.runtime = next_runtime
            projection.last_accessed_at = consumed_at
            projection.projection_updates += 1
            projection.last_event_id = str(entry.get("entry_id") or entry.get("event_id") or "") or None
            projection.last_event_ts = ts
            projection.last_event_consumed_at = consumed_at
            backend = projection.backend
            filters = dict(projection.filters)
        await self._store_snapshot(backend, filters, next_workspace)
        return {**next_workspace}

    async def _broadcast_authoritative_snapshot(self, projection_key: str) -> None:
        await asyncio.sleep(0.25)
        async with self.authoritative_lock:
            projection = self.authoritative_projections.get(projection_key)
            if projection is None:
                return
            payload = {**projection.workspace}
            emitted_at = now_iso()
            projection.snapshot_emits += 1
            projection.last_snapshot_emitted_at = emitted_at
            if projection.last_event_consumed_at:
                consumed_at_dt = parse_timestamp(projection.last_event_consumed_at)
                emitted_at_dt = parse_timestamp(emitted_at)
                if consumed_at_dt and emitted_at_dt:
                    projection.last_emit_lag_ms = max((emitted_at_dt - consumed_at_dt).total_seconds() * 1000.0, 0.0)
            if projection.last_event_ts:
                event_ts_dt = parse_timestamp(projection.last_event_ts)
                emitted_at_dt = parse_timestamp(emitted_at)
                if event_ts_dt and emitted_at_dt:
                    projection.last_event_age_at_emit_ms = max((emitted_at_dt - event_ts_dt).total_seconds() * 1000.0, 0.0)
            backend = projection.backend
            filters = dict(projection.filters)
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
        await self.manager.broadcast(backend, message, matcher=lambda subscription: subscription.filters == filters)

    def _schedule_authoritative_broadcast(self, projection_key: str) -> None:
        existing = self.authoritative_broadcast_tasks.get(projection_key)
        if existing is not None and not existing.done():
            return
        task = asyncio.create_task(self._broadcast_authoritative_snapshot(projection_key))
        self.authoritative_broadcast_tasks[projection_key] = task
        self._track_background_task(task)

    async def _bootstrap_authoritative_projection(self, backend: str, filters: dict[str, str] | None = None) -> dict[str, Any] | None:
        normalized_filters = dict(filters or {})
        payload = await self.fetch_workspace(backend, normalized_filters)
        if payload is None:
            return None
        return await self._set_authoritative_projection(backend, normalized_filters, payload)

    async def _release_authoritative_projection_if_idle(self, backend: str, filters: dict[str, str] | None = None) -> None:
        normalized_filters = dict(filters or {})
        if not normalized_filters:
            return
        subscriptions = await self.manager.subscriptions(backend)
        for _, subscription in subscriptions:
            if subscription.filters == normalized_filters:
                return
        projection_key = self._projection_cache_key(backend, normalized_filters)
        async with self.authoritative_lock:
            self.authoritative_projections.pop(projection_key, None)
        self.authoritative_broadcast_tasks.pop(projection_key, None)

    async def _authoritative_metrics(self) -> dict[str, Any]:
        async with self.authoritative_lock:
            projections = list(self.authoritative_projections.values())
        return {
            "enabled_backends": sorted(self.authoritative_projection_backends),
            "supported_filters": sorted(self.authoritative_supported_filters),
            "active_projection_count": len(projections),
            "filtered_projection_count": sum(1 for projection in projections if projection.filters),
            "projections": [
                {
                    "backend": projection.backend,
                    "filters": projection.filters,
                    "created_at": projection.created_at,
                    "last_accessed_at": projection.last_accessed_at,
                    "projection_updates": projection.projection_updates,
                    "snapshot_emits": projection.snapshot_emits,
                    "last_event_id": projection.last_event_id,
                    "last_event_ts": projection.last_event_ts,
                    "last_event_consumed_at": projection.last_event_consumed_at,
                    "last_snapshot_emitted_at": projection.last_snapshot_emitted_at,
                    "last_emit_lag_ms": projection.last_emit_lag_ms,
                    "last_event_age_at_emit_ms": projection.last_event_age_at_emit_ms,
                }
                for projection in projections[:24]
            ],
        }

    async def _refresh_workspace_snapshot(self, backend: str, filters: dict[str, str] | None = None) -> dict[str, Any] | None:
        cache_key = self._snapshot_cache_key(backend, filters)
        async with self.snapshot_lock:
            inflight = self.snapshot_refresh_tasks.get(cache_key)
            if inflight is None or inflight.done():
                inflight = asyncio.create_task(self.fetch_workspace(backend, filters))
                self.snapshot_refresh_tasks[cache_key] = inflight

        try:
            payload = await inflight
        finally:
            async with self.snapshot_lock:
                current = self.snapshot_refresh_tasks.get(cache_key)
                if current is inflight:
                    self.snapshot_refresh_tasks.pop(cache_key, None)

        if payload is None:
            return await self._snapshot_from_cache(backend, filters)
        return await self._store_snapshot(backend, filters, payload)

    async def _send_snapshot_message(self, websocket: WebSocket, backend: str, payload: dict[str, Any]) -> None:
        await websocket.send_json(
            {
                "event_id": f"dashboard-{backend}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "event_type": "dashboard.snapshot",
                "version": "1.0.0",
                "backend": backend,
                "ts": now_iso(),
                "payload": payload,
            }
        )

    async def _refresh_and_send_snapshot(self, websocket: WebSocket, backend: str, filters: dict[str, str] | None, previous_timestamp: str | None) -> None:
        payload = await self._refresh_workspace_snapshot(backend, filters)
        if payload is None:
            return
        next_timestamp = str(payload.get("timestamp") or "")
        if previous_timestamp and next_timestamp == previous_timestamp:
            return
        try:
            await self._send_snapshot_message(websocket, backend, payload)
        except Exception:
            return

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
        normalized_filters = dict(filters or {})
        if self._uses_authoritative_projection(backend, normalized_filters):
            payload = await self._get_authoritative_projection(backend, normalized_filters)
            if payload is None:
                payload = await self._bootstrap_authoritative_projection(backend, normalized_filters)
            if payload is None:
                return
            if websocket is not None:
                await self._send_snapshot_message(websocket, backend, payload)
                return
            if connection_id is not None:
                subscription = await self.manager.subscription(backend, connection_id)
                if subscription is None:
                    return
                await self._send_snapshot_message(subscription.websocket, backend, payload)
                return
            message = {
                "event_id": f"dashboard-{backend}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "event_type": "dashboard.snapshot",
                "version": "1.0.0",
                "backend": backend,
                "ts": now_iso(),
                "payload": payload,
            }
            await self.manager.broadcast(backend, message, matcher=lambda subscription: subscription.filters == normalized_filters)
            return
        cached_payload = await self._snapshot_from_cache(backend, normalized_filters)
        payload = cached_payload or await self._refresh_workspace_snapshot(backend, normalized_filters)
        if payload is None:
            return
        if websocket is not None:
            await self._send_snapshot_message(websocket, backend, payload)
            if cached_payload is not None:
                refresh_task = asyncio.create_task(
                    self._refresh_and_send_snapshot(
                        websocket,
                        backend,
                        normalized_filters,
                        str(cached_payload.get("timestamp") or ""),
                    )
                )
                self._track_background_task(refresh_task)
            return
        if connection_id is not None:
            subscription = await self.manager.subscription(backend, connection_id)
            if subscription is None:
                return
            await self._send_snapshot_message(subscription.websocket, backend, payload)
            return
        message = {
            "event_id": f"dashboard-{backend}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            "event_type": "dashboard.snapshot",
            "version": "1.0.0",
            "backend": backend,
            "ts": now_iso(),
            "payload": payload,
        }
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
                consumed_at = now_iso()

                for backend in self.active_backends:
                    async with self.authoritative_lock:
                        projection_candidates = [
                            (projection_key, projection.backend, dict(projection.filters))
                            for projection_key, projection in self.authoritative_projections.items()
                            if projection.backend == backend
                        ]
                    event_ts = str(entry.get("ingested_at") or entry.get("occurred_at") or now_iso())
                    for projection_key, _, projection_filters in projection_candidates:
                        if entry_matches_filters(entry, projection_filters):
                            await self._apply_authoritative_projection(projection_key, entry, event_ts, consumed_at)
                            self._schedule_authoritative_broadcast(projection_key)
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
    for backend in gateway.active_backends:
        if backend in gateway.authoritative_projection_backends:
            gateway._track_background_task(asyncio.create_task(gateway._bootstrap_authoritative_projection(backend)))
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
        "authoritative_projection": await gateway._authoritative_metrics(),
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
            await gateway._release_authoritative_projection_if_idle(requested_backend, filters)