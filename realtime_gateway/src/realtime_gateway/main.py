import asyncio
import json
import os
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import httpx
from confluent_kafka import Consumer
from fastapi import FastAPI, WebSocket, WebSocketDisconnect


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_backends() -> list[str]:
    configured = os.getenv("ACTIVE_STACKS", "clickhouse,druid,pinot")
    ordered = ["clickhouse", "druid", "pinot"]
    enabled = {item.strip() for item in configured.split(",") if item.strip()}
    return [backend for backend in ordered if backend in enabled]


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[str, dict[str, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def register(self, websocket: WebSocket, backend: str) -> str:
        connection_id = str(uuid.uuid4())
        async with self._lock:
            self._connections[backend][connection_id] = websocket
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

    async def broadcast(self, backend: str, message: dict[str, Any]) -> None:
        async with self._lock:
            targets = list(self._connections.get(backend, {}).items())

        stale_connection_ids: list[str] = []
        for connection_id, websocket in targets:
            try:
                await websocket.send_json(message)
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
        self.coalesce_seconds = max(int(os.getenv("REALTIME_GATEWAY_COALESCE_MS", "250")), 50) / 1000
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
        self.snapshot_tasks: dict[str, asyncio.Task[Any]] = {}
        self.consumer_task: asyncio.Task[Any] | None = None
        self.state: dict[str, Any] = {
            "state": "idle",
            "topic": self.topic,
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
        for task in self.snapshot_tasks.values():
            task.cancel()
        await self.client.aclose()
        await asyncio.to_thread(self.consumer.close)

    async def fetch_workspace(self, backend: str) -> dict[str, Any] | None:
        base_url = self.backend_urls.get(backend)
        if not base_url:
            return None
        try:
            response = await self.client.get(f"{base_url}/api/v1/dashboard/workspace")
            response.raise_for_status()
            payload = response.json()
            if isinstance(payload, dict):
                payload["backend"] = backend
                return payload
        except Exception as exc:
            self.state["last_error"] = f"workspace:{backend}:{exc}"
        return None

    async def send_snapshot(self, backend: str, websocket: WebSocket | None = None) -> None:
        payload = await self.fetch_workspace(backend)
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
        await self.manager.broadcast(backend, message)

    def schedule_snapshot(self, backend: str) -> None:
        if backend not in self.active_backends:
            return
        existing = self.snapshot_tasks.get(backend)
        if existing and not existing.done():
            return
        self.snapshot_tasks[backend] = asyncio.create_task(self._flush_snapshot(backend))

    async def _flush_snapshot(self, backend: str) -> None:
        await asyncio.sleep(self.coalesce_seconds)
        if await self.manager.has_backend_subscribers(backend):
            await self.send_snapshot(backend)

    async def consume(self) -> None:
        while True:
            try:
                message = await asyncio.to_thread(self.consumer.poll, 1.0)
                if message is None:
                    self.state["state"] = "idle"
                    continue

                if message.error():
                    self.state["state"] = "error"
                    self.state["last_error"] = str(message.error())
                    await asyncio.sleep(1)
                    continue

                entry = json.loads(message.value().decode("utf-8"))
                self.state["state"] = "running"
                self.state["messages_processed"] = int(self.state.get("messages_processed", 0)) + 1
                self.state["last_event_id"] = entry.get("event_id")
                self.state["last_offsets"] = {
                    "topic": message.topic(),
                    "partition": message.partition(),
                    "offset": message.offset(),
                }

                for backend in self.active_backends:
                    if not await self.manager.has_backend_subscribers(backend):
                        continue
                    await self.manager.broadcast(
                        backend,
                        {
                            "event_id": entry.get("entry_id") or entry.get("event_id") or str(uuid.uuid4()),
                            "event_type": "entry.created",
                            "version": "1.0.0",
                            "backend": backend,
                            "ts": str(entry.get("ingested_at") or entry.get("occurred_at") or now_iso()),
                            "payload": entry,
                        },
                    )
                    self.schedule_snapshot(backend)

                await asyncio.to_thread(self.consumer.commit, message=message, asynchronous=False)
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
    try:
        await gateway.send_snapshot(requested_backend, websocket)
        connection_id = await gateway.manager.register(websocket, requested_backend)
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        return
    finally:
        if 'connection_id' in locals():
            await gateway.manager.disconnect(requested_backend, connection_id)