import json
import os
import gzip
from base64 import b64decode
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest

from storage_writer.adapters import ClickHouseAdapter, DruidAdapter, PinotAdapter

app = FastAPI(title="synthetic-ledger-storage-writer", version="0.1.0")
last_otlp_stats: dict[str, Any] = {}


def build_adapters() -> dict[str, Any]:
    registry = {
        "clickhouse": ClickHouseAdapter,
        "druid": DruidAdapter,
        "pinot": PinotAdapter,
    }
    enabled = [item.strip() for item in os.getenv("TARGET_BACKENDS", "clickhouse,druid,pinot").split(",") if item.strip()]
    return {name: registry[name]() for name in enabled if name in registry}


adapters = build_adapters()


@app.get("/health")
async def health() -> dict[str, Any]:
    statuses = {}
    for name, adapter in adapters.items():
        statuses[name] = await adapter.healthy()
    return {"status": "ok", "adapters": statuses}


@app.get("/debug/last-otlp")
async def debug_last_otlp() -> dict[str, Any]:
    return last_otlp_stats


@app.post("/v1/logs")
async def ingest_otlp_logs(request: Request) -> dict[str, Any]:
    global last_otlp_stats
    raw = await request.body()
    if not raw:
        last_otlp_stats = {"payload_bytes": 0, "accepted": 0, "written": 0}
        return {"accepted": 0, "written": 0}

    if request.headers.get("content-encoding", "").lower() == "gzip" or raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)

    content_type = request.headers.get("content-type", "")

    events: list[dict[str, Any]] = []

    if "json" in content_type:
        payload = json.loads(raw.decode("utf-8"))
        for resource_log in payload.get("resourceLogs", []):
            for scope_log in resource_log.get("scopeLogs", []):
                for log_record in scope_log.get("logRecords", []):
                    body = log_record.get("body", {})
                    if "stringValue" in body:
                        try:
                            events.append(json.loads(body["stringValue"]))
                        except json.JSONDecodeError:
                            continue
                    elif "bytesValue" in body:
                        try:
                            decoded = b64decode(body["bytesValue"]).decode("utf-8")
                            events.append(json.loads(decoded))
                        except Exception:
                            continue
    else:
        envelope = ExportLogsServiceRequest()
        envelope.ParseFromString(raw)
        for resource_log in envelope.resource_logs:
            for scope_log in resource_log.scope_logs:
                for log_record in scope_log.log_records:
                    body = log_record.body
                    if body.string_value:
                        try:
                            events.append(json.loads(body.string_value))
                        except json.JSONDecodeError:
                            continue
                    elif body.bytes_value:
                        try:
                            events.append(json.loads(body.bytes_value.decode("utf-8")))
                        except Exception:
                            nested = ExportLogsServiceRequest()
                            try:
                                nested.ParseFromString(body.bytes_value)
                                for nested_resource in nested.resource_logs:
                                    for nested_scope in nested_resource.scope_logs:
                                        for nested_record in nested_scope.log_records:
                                            if nested_record.body.string_value:
                                                try:
                                                    events.append(json.loads(nested_record.body.string_value))
                                                except json.JSONDecodeError:
                                                    continue
                            except Exception:
                                continue

    if not events:
        last_otlp_stats = {
            "payload_bytes": len(raw),
            "content_type": content_type,
            "accepted": 0,
            "written": 0,
            "backend_writes": {},
            "backend_errors": {},
        }
        return {"accepted": 0, "written": 0}

    active_adapters: dict[str, Any] = {}
    for name, adapter in adapters.items():
        if await adapter.healthy():
            active_adapters[name] = adapter

    written = 0
    backend_writes: dict[str, int] = {name: 0 for name in active_adapters.keys()}
    backend_errors: dict[str, str] = {}
    for event in events:
        for name, adapter in active_adapters.items():
            try:
                await adapter.write_event(event)
                written += 1
                backend_writes[name] += 1
            except Exception as exc:
                backend_errors[name] = str(exc)
                continue

    if written == 0:
        last_otlp_stats = {
            "payload_bytes": len(raw),
            "content_type": content_type,
            "accepted": len(events),
            "written": written,
            "backend_writes": backend_writes,
            "backend_errors": backend_errors,
        }
        raise HTTPException(status_code=503, detail="No backend available for write")

    last_otlp_stats = {
        "payload_bytes": len(raw),
        "content_type": content_type,
        "accepted": len(events),
        "written": written,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }

    return {
        "accepted": len(events),
        "written": written,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }


@app.post("/ingest")
async def ingest_direct(request: Request) -> dict[str, Any]:
    event = await request.json()
    written = 0
    active_adapters: dict[str, Any] = {}
    for name, adapter in adapters.items():
        if await adapter.healthy():
            active_adapters[name] = adapter

    backend_writes: dict[str, int] = {name: 0 for name in active_adapters.keys()}
    backend_errors: dict[str, str] = {}
    for name, adapter in active_adapters.items():
        try:
            await adapter.write_event(event)
            written += 1
            backend_writes[name] += 1
        except Exception as exc:
            backend_errors[name] = str(exc)
            continue
    return {
        "accepted": 1,
        "written": written,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }
