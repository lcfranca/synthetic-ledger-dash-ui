import json
import os
import gzip
import uuid
import hashlib
from base64 import b64decode
from datetime import datetime, timezone
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


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def account_name(account_code: str) -> str:
    if "-" in account_code:
        return account_code.split("-", maxsplit=1)[1]
    return account_code


def statement_section(account_code: str) -> str:
    if account_code.startswith("1."):
        return "asset"
    if account_code.startswith("2."):
        return "liability"
    if account_code.startswith("3."):
        return "revenue"
    if account_code.startswith("4."):
        return "expense"
    return "other"


def make_entry(
    *,
    event: dict[str, Any],
    entry_side: str,
    account_code: str,
    amount: float,
    ontology_description: str,
    payload_hash: str,
    ontology_source: str = "synthetic_producer",
) -> dict[str, Any]:
    section = statement_section(account_code)
    sign = 1.0 if entry_side == "debit" else -1.0
    occurred_at = event.get("occurred_at", now_iso())
    ingested_at = event.get("ingested_at", now_iso())

    return {
        "entry_id": str(uuid.uuid4()),
        "event_id": event["event_id"],
        "trace_id": event["event_id"],
        "company_id": event["company_id"],
        "tenant_id": event["tenant_id"],
        "entry_side": entry_side,
        "account_code": account_code,
        "account_name": account_name(account_code),
        "statement_section": section,
        "amount": round(amount, 2),
        "signed_amount": round(amount * sign, 2),
        "currency": event.get("currency", "BRL"),
        "ontology_event_type": event.get("event_type", "unknown"),
        "ontology_description": ontology_description,
        "ontology_source": ontology_source,
        "source_payload_hash": payload_hash,
        "schema_version": event.get("schema_version", "1.0.0"),
        "occurred_at": occurred_at,
        "ingested_at": ingested_at,
        "valid_from": ingested_at,
        "valid_to": None,
        "is_current": 1,
        "revision": 1,
        "created_at": now_iso(),
    }


def event_to_journal_entries(event: dict[str, Any]) -> list[dict[str, Any]]:
    gross = float(event.get("quantity", 0)) * float(event.get("unit_price", 0))
    discount = float(event.get("discount", 0))
    tax = float(event.get("tax", 0))
    amount = max(gross - discount + tax, 0.0)
    cmv = float(event.get("cmv", 0.0))

    canonical_event = {
        **event,
        "occurred_at": event.get("occurred_at", now_iso()),
        "ingested_at": event.get("ingested_at", now_iso()),
    }
    payload_hash = hashlib.sha256(json.dumps(canonical_event, sort_keys=True).encode("utf-8")).hexdigest()

    event_type = canonical_event.get("event_type")
    if event_type == "purchase":
        return [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code="1.1.03.01-Estoque",
                amount=amount,
                ontology_description="Compra de estoque com reconhecimento de ativo.",
                payload_hash=payload_hash,
            ),
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code="1.1.01.01-Caixa",
                amount=amount,
                ontology_description="Saída de caixa associada à compra.",
                payload_hash=payload_hash,
            ),
        ]

    if event_type == "sale":
        entries = [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code="1.1.01.01-Caixa",
                amount=amount,
                ontology_description="Entrada de caixa por venda.",
                payload_hash=payload_hash,
            ),
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code="3.1.01.01-Receita",
                amount=amount,
                ontology_description="Reconhecimento de receita de venda.",
                payload_hash=payload_hash,
            ),
        ]
        if cmv > 0:
            entries.extend(
                [
                    make_entry(
                        event=canonical_event,
                        entry_side="debit",
                        account_code="4.1.01.01-CMV",
                        amount=cmv,
                        ontology_description="Reconhecimento do custo da mercadoria vendida.",
                        payload_hash=payload_hash,
                    ),
                    make_entry(
                        event=canonical_event,
                        entry_side="credit",
                        account_code="1.1.03.01-Estoque",
                        amount=cmv,
                        ontology_description="Baixa de estoque por venda.",
                        payload_hash=payload_hash,
                    ),
                ]
            )
        return entries

    return [
        make_entry(
            event=canonical_event,
            entry_side="debit",
            account_code=str(canonical_event.get("debit_account", "1.1.01.01-Caixa")),
            amount=amount,
            ontology_description="Lançamento de débito derivado de evento canônico.",
            payload_hash=payload_hash,
        ),
        make_entry(
            event=canonical_event,
            entry_side="credit",
            account_code=str(canonical_event.get("credit_account", "3.1.01.01-Receita")),
            amount=amount,
            ontology_description="Lançamento de crédito derivado de evento canônico.",
            payload_hash=payload_hash,
        ),
    ]


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

    entries: list[dict[str, Any]] = []
    for event in events:
        if "event_id" not in event:
            continue
        entries.extend(event_to_journal_entries(event))

    if not entries:
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
    for entry in entries:
        for name, adapter in active_adapters.items():
            try:
                await adapter.write_event(entry)
                written += 1
                backend_writes[name] += 1
            except Exception as exc:
                backend_errors[name] = str(exc)
                continue

    if written == 0:
        last_otlp_stats = {
            "payload_bytes": len(raw),
            "content_type": content_type,
            "accepted": len(entries),
            "written": written,
            "backend_writes": backend_writes,
            "backend_errors": backend_errors,
        }
        raise HTTPException(status_code=503, detail="No backend available for write")

    last_otlp_stats = {
        "payload_bytes": len(raw),
        "content_type": content_type,
        "accepted": len(entries),
        "written": written,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }

    return {
        "accepted": len(entries),
        "written": written,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }


@app.post("/ingest")
async def ingest_direct(request: Request) -> dict[str, Any]:
    event = await request.json()
    entries = event_to_journal_entries(event)
    written = 0
    active_adapters: dict[str, Any] = {}
    for name, adapter in adapters.items():
        if await adapter.healthy():
            active_adapters[name] = adapter

    backend_writes: dict[str, int] = {name: 0 for name in active_adapters.keys()}
    backend_errors: dict[str, str] = {}
    for entry in entries:
        for name, adapter in active_adapters.items():
            try:
                await adapter.write_event(entry)
                written += 1
                backend_writes[name] += 1
            except Exception as exc:
                backend_errors[name] = str(exc)
                continue
    return {
        "accepted": len(entries),
        "written": written,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }
