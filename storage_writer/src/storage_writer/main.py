import json
import os
import gzip
import asyncio
import uuid
import hashlib
from base64 import b64decode
from datetime import datetime, timezone
from typing import Any

import httpx
from confluent_kafka import Producer
from fastapi import FastAPI, HTTPException, Request
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest

from storage_writer.adapters import ClickHouseAdapter, DruidAdapter, PinotAdapter

app = FastAPI(title="synthetic-ledger-storage-writer", version="0.1.0")
last_otlp_stats: dict[str, Any] = {}
druid_supervisor_status: dict[str, Any] = {}
pinot_realtime_status: dict[str, Any] = {}


def build_adapters() -> dict[str, Any]:
    registry = {
        "clickhouse": ClickHouseAdapter,
        "druid": DruidAdapter,
        "pinot": PinotAdapter,
    }
    enabled = [item.strip() for item in os.getenv("TARGET_BACKENDS", "clickhouse,druid,pinot").split(",") if item.strip()]
    return {name: registry[name]() for name in enabled if name in registry}


adapters = build_adapters()


def is_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def build_entries_kafka_producer() -> Producer | None:
    if not is_true("DRUID_KAFKA_PUBLISH_ENABLED", "true"):
        return None
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return Producer({"bootstrap.servers": bootstrap, "linger.ms": 10, "batch.num.messages": 1000})


entries_kafka_producer = build_entries_kafka_producer()


def publish_entry_to_kafka(entry: dict[str, Any]) -> bool:
    if entries_kafka_producer is None:
        return False
    topic = os.getenv("DRUID_KAFKA_TOPIC", "ledger-entries-v1")
    try:
        entries_kafka_producer.produce(
            topic=topic,
            key=str(entry.get("company_id", "unknown")),
            value=json.dumps(entry, separators=(",", ":")).encode("utf-8"),
        )
        entries_kafka_producer.poll(0)
        return True
    except Exception:
        return False


async def ensure_druid_kafka_supervisor() -> None:
    global druid_supervisor_status
    if not is_true("DRUID_KAFKA_CONSUMER_ENABLED", "true"):
        druid_supervisor_status = {"enabled": False, "reason": "DRUID_KAFKA_CONSUMER_ENABLED=false"}
        return

    if "druid" not in adapters:
        druid_supervisor_status = {"enabled": False, "reason": "druid adapter disabled"}
        return

    topic = os.getenv("DRUID_KAFKA_TOPIC", "ledger-entries-v1")
    datasource = os.getenv("DRUID_DATASOURCE", "ledger_events")
    druid_url = os.getenv("DRUID_OVERLORD_URL", "http://druid-overlord:8081")
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

    supervisor_spec = {
        "type": "kafka",
        "spec": {
            "dataSchema": {
                "dataSource": datasource,
                "timestampSpec": {"column": "occurred_at", "format": "auto"},
                "dimensionsSpec": {
                    "dimensions": [
                        "entry_id",
                        "event_id",
                        "trace_id",
                        "company_id",
                        "tenant_id",
                        "entry_side",
                        "account_code",
                        "account_name",
                        "statement_section",
                        "currency",
                        "ontology_event_type",
                        "ontology_description",
                        "ontology_source",
                        "product_id",
                        "supplier_id",
                        "customer_id",
                        "warehouse_id",
                        "channel",
                        "entry_category",
                        "source_payload_hash",
                        "schema_version",
                        "ingested_at",
                        "valid_from",
                        "valid_to",
                    ]
                },
                "metricsSpec": [
                    {"type": "doubleSum", "name": "amount", "fieldName": "amount"},
                    {"type": "doubleSum", "name": "signed_amount", "fieldName": "signed_amount"},
                    {"type": "longMax", "name": "revision", "fieldName": "revision"},
                    {"type": "longMax", "name": "is_current", "fieldName": "is_current"},
                ],
                "granularitySpec": {
                    "type": "uniform",
                    "segmentGranularity": "HOUR",
                    "queryGranularity": "NONE",
                    "rollup": False,
                },
            },
            "ioConfig": {
                "type": "kafka",
                "topic": topic,
                "consumerProperties": {"bootstrap.servers": kafka_bootstrap},
                "inputFormat": {"type": "json"},
                "useEarliestOffset": True,
            },
            "tuningConfig": {"type": "kafka"},
        },
    }

    last_error = ""
    retry_seconds = max(int(os.getenv("DRUID_SUPERVISOR_RETRY_SECONDS", "5")), 1)
    max_attempts = int(os.getenv("DRUID_SUPERVISOR_MAX_ATTEMPTS", "0"))
    attempt = 0
    while max_attempts <= 0 or attempt < max_attempts:
        attempt += 1
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                response = await client.post(f"{druid_url}/druid/indexer/v1/supervisor", json=supervisor_spec)
                response.raise_for_status()
                payload = response.json()
                supervisor_id = payload.get("id") or payload.get("supervisorId")
                druid_supervisor_status = {
                    "enabled": True,
                    "topic": topic,
                    "datasource": datasource,
                    "supervisor_id": supervisor_id,
                    "attempt": attempt,
                    "raw": payload,
                }
                return
        except Exception as exc:
            last_error = str(exc)
            druid_supervisor_status = {
                "enabled": False,
                "state": "retrying",
                "topic": topic,
                "datasource": datasource,
                "attempt": attempt,
                "error": last_error,
                "retry_in_seconds": retry_seconds,
            }
            await asyncio.sleep(retry_seconds)

    druid_supervisor_status = {
        "enabled": False,
        "state": "failed",
        "topic": topic,
        "datasource": datasource,
        "attempt": attempt,
        "error": last_error,
    }


async def bootstrap_druid_supervisor_task() -> None:
    global druid_supervisor_status
    druid_supervisor_status = {"enabled": False, "state": "starting"}
    try:
        await ensure_druid_kafka_supervisor()
    except Exception as exc:
        druid_supervisor_status = {
            "enabled": False,
            "state": "failed",
            "error": str(exc),
        }


async def ensure_pinot_kafka_realtime_table() -> None:
    global pinot_realtime_status
    if not is_true("PINOT_KAFKA_CONSUMER_ENABLED", "true"):
        pinot_realtime_status = {"enabled": False, "reason": "PINOT_KAFKA_CONSUMER_ENABLED=false"}
        return

    if "pinot" not in adapters:
        pinot_realtime_status = {"enabled": False, "reason": "pinot adapter disabled"}
        return

    controller_url = os.getenv("PINOT_CONTROLLER_URL", "http://pinot-controller:9000")
    table = os.getenv("PINOT_TABLE", "ledger_events")
    topic = os.getenv("DRUID_KAFKA_TOPIC", "ledger-entries-v1")
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")

    schema_name = table
    realtime_table_name = f"{table}_REALTIME"

    schema_payload = {
        "schemaName": schema_name,
        "dimensionFieldSpecs": [
            {"name": "entry_id", "dataType": "STRING"},
            {"name": "event_id", "dataType": "STRING"},
            {"name": "trace_id", "dataType": "STRING"},
            {"name": "company_id", "dataType": "STRING"},
            {"name": "tenant_id", "dataType": "STRING"},
            {"name": "entry_side", "dataType": "STRING"},
            {"name": "account_code", "dataType": "STRING"},
            {"name": "account_name", "dataType": "STRING"},
            {"name": "statement_section", "dataType": "STRING"},
            {"name": "currency", "dataType": "STRING"},
            {"name": "ontology_event_type", "dataType": "STRING"},
            {"name": "ontology_description", "dataType": "STRING"},
            {"name": "ontology_source", "dataType": "STRING"},
            {"name": "product_id", "dataType": "STRING"},
            {"name": "supplier_id", "dataType": "STRING"},
            {"name": "customer_id", "dataType": "STRING"},
            {"name": "warehouse_id", "dataType": "STRING"},
            {"name": "channel", "dataType": "STRING"},
            {"name": "entry_category", "dataType": "STRING"},
            {"name": "source_payload_hash", "dataType": "STRING"},
            {"name": "schema_version", "dataType": "STRING"},
            {"name": "occurred_at", "dataType": "STRING"},
            {"name": "ingested_at", "dataType": "STRING"},
            {"name": "valid_from", "dataType": "STRING"},
            {"name": "valid_to", "dataType": "STRING"},
            {"name": "created_at", "dataType": "STRING"},
        ],
        "metricFieldSpecs": [
            {"name": "amount", "dataType": "DOUBLE"},
            {"name": "signed_amount", "dataType": "DOUBLE"},
            {"name": "is_current", "dataType": "INT"},
            {"name": "revision", "dataType": "INT"},
        ],
        "dateTimeFieldSpecs": [
            {
                "name": "occurred_at_epoch_ms",
                "dataType": "LONG",
                "format": "1:MILLISECONDS:EPOCH",
                "granularity": "1:MILLISECONDS",
            }
        ],
    }

    table_payload = {
        "tableName": realtime_table_name,
        "tableType": "REALTIME",
        "segmentsConfig": {
            "timeColumnName": "occurred_at_epoch_ms",
            "schemaName": schema_name,
            "replication": "1",
        },
        "tenants": {"broker": "DefaultTenant", "server": "DefaultTenant"},
        "tableIndexConfig": {
            "loadMode": "MMAP",
            "streamConfigs": {
                "streamType": "kafka",
                "stream.kafka.topic.name": topic,
                "stream.kafka.broker.list": kafka_bootstrap,
                "stream.kafka.consumer.type": "lowlevel",
                "stream.kafka.decoder.class.name": "org.apache.pinot.plugin.stream.kafka.KafkaJSONMessageDecoder",
                "stream.kafka.consumer.prop.auto.offset.reset": "smallest",
            },
        },
        "ingestionConfig": {
            "continueOnError": True,
            "rowTimeValueCheck": False,
        },
        "metadata": {},
    }

    retry_seconds = max(int(os.getenv("PINOT_BOOTSTRAP_RETRY_SECONDS", "5")), 1)
    max_attempts = int(os.getenv("PINOT_BOOTSTRAP_MAX_ATTEMPTS", "0"))
    attempt = 0
    last_error = ""

    while max_attempts <= 0 or attempt < max_attempts:
        attempt += 1
        try:
            async with httpx.AsyncClient(timeout=10.0, follow_redirects=True) as client:
                schema_get = await client.get(f"{controller_url}/schemas/{schema_name}")
                if schema_get.status_code == 404:
                    schema_create = await client.post(f"{controller_url}/schemas", json=schema_payload)
                    schema_create.raise_for_status()
                elif schema_get.status_code >= 400:
                    schema_get.raise_for_status()
                else:
                    current_schema = schema_get.json()
                    current_fields = {
                        item.get("name")
                        for group in (
                            current_schema.get("dimensionFieldSpecs", []),
                            current_schema.get("metricFieldSpecs", []),
                            current_schema.get("dateTimeFieldSpecs", []),
                        )
                        for item in group
                        if isinstance(item, dict)
                    }
                    if "occurred_at_epoch_ms" not in current_fields:
                        schema_update = await client.put(f"{controller_url}/schemas/{schema_name}", json=schema_payload)
                        schema_update.raise_for_status()

                tables_response = await client.get(f"{controller_url}/tables")
                tables_response.raise_for_status()
                existing_tables = set((tables_response.json() or {}).get("tables", []))
                has_realtime_table = realtime_table_name in existing_tables or table in existing_tables

                if not has_realtime_table:
                    table_create = await client.post(f"{controller_url}/tables", json=table_payload)
                    table_create.raise_for_status()

                tables_verify = await client.get(f"{controller_url}/tables")
                tables_verify.raise_for_status()
                verified_tables = set((tables_verify.json() or {}).get("tables", []))
                has_realtime_table = realtime_table_name in verified_tables or table in verified_tables
                if not has_realtime_table:
                    raise RuntimeError("Pinot realtime table was not registered in controller")

                pinot_realtime_status = {
                    "enabled": True,
                    "table": realtime_table_name,
                    "topic": topic,
                    "attempt": attempt,
                    "controller_url": controller_url,
                    "state": "ready",
                }
                return
        except Exception as exc:
            last_error = str(exc)
            pinot_realtime_status = {
                "enabled": False,
                "state": "retrying",
                "table": realtime_table_name,
                "topic": topic,
                "attempt": attempt,
                "error": last_error,
                "retry_in_seconds": retry_seconds,
            }
            await asyncio.sleep(retry_seconds)

    pinot_realtime_status = {
        "enabled": False,
        "state": "failed",
        "table": realtime_table_name,
        "topic": topic,
        "attempt": attempt,
        "error": last_error,
    }


async def bootstrap_pinot_realtime_task() -> None:
    global pinot_realtime_status
    pinot_realtime_status = {"enabled": False, "state": "starting"}
    try:
        await ensure_pinot_kafka_realtime_table()
    except Exception as exc:
        pinot_realtime_status = {
            "enabled": False,
            "state": "failed",
            "error": str(exc),
        }


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def to_epoch_millis(value: str) -> int:
    normalized = value.replace("Z", "+00:00")
    try:
        return int(datetime.fromisoformat(normalized).timestamp() * 1000)
    except ValueError:
        return int(datetime.now(timezone.utc).timestamp() * 1000)


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


def entry_category(account_code: str, event_type: str) -> str:
    if account_code.startswith("3."):
        return "receita"
    if account_code.startswith("4."):
        return "cmv_despesa"
    if account_code == "1.1.03.01-Estoque":
        return "estoque"
    if account_code == "1.1.01.01-Caixa":
        return "caixa"
    if event_type == "purchase":
        return "suprimentos"
    if event_type == "sale":
        return "comercial"
    return "operacional"


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
    canonical_event_type = str(event.get("event_type", "unknown"))
    product_id = str(event.get("product_id", "unknown-product"))
    supplier_id = event.get("supplier_id")
    customer_id = event.get("customer_id")
    warehouse_id = str(event.get("warehouse_id", "unknown-warehouse"))
    channel = str(event.get("channel", "unknown-channel"))

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
        "ontology_event_type": canonical_event_type,
        "ontology_description": ontology_description,
        "ontology_source": ontology_source,
        "product_id": product_id,
        "supplier_id": supplier_id,
        "customer_id": customer_id,
        "warehouse_id": warehouse_id,
        "channel": channel,
        "entry_category": entry_category(account_code, canonical_event_type),
        "source_payload_hash": payload_hash,
        "schema_version": event.get("schema_version", "1.0.0"),
        "occurred_at": occurred_at,
        "occurred_at_epoch_ms": to_epoch_millis(occurred_at),
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


@app.get("/debug/druid-supervisor")
async def debug_druid_supervisor() -> dict[str, Any]:
    return druid_supervisor_status


@app.get("/debug/pinot-realtime")
async def debug_pinot_realtime() -> dict[str, Any]:
    return pinot_realtime_status


@app.on_event("startup")
async def startup_tasks() -> None:
    asyncio.create_task(bootstrap_druid_supervisor_task())
    asyncio.create_task(bootstrap_pinot_realtime_task())


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
        if name == "druid" and not is_true("DRUID_DIRECT_WRITE_ENABLED", "false"):
            continue
        if name == "pinot" and not is_true("PINOT_DIRECT_WRITE_ENABLED", "false"):
            continue
        if await adapter.healthy():
            active_adapters[name] = adapter

    written = 0
    kafka_published = 0
    backend_writes: dict[str, int] = {name: 0 for name in active_adapters.keys()}
    backend_errors: dict[str, str] = {}
    for entry in entries:
        if publish_entry_to_kafka(entry):
            kafka_published += 1
        for name, adapter in active_adapters.items():
            try:
                await adapter.write_event(entry)
                written += 1
                backend_writes[name] += 1
            except Exception as exc:
                backend_errors[name] = str(exc)
                continue

    if written == 0 and kafka_published == 0:
        last_otlp_stats = {
            "payload_bytes": len(raw),
            "content_type": content_type,
            "accepted": len(entries),
            "written": written,
            "kafka_published": kafka_published,
            "backend_writes": backend_writes,
            "backend_errors": backend_errors,
        }
        raise HTTPException(status_code=503, detail="No backend or kafka topic available for write")

    last_otlp_stats = {
        "payload_bytes": len(raw),
        "content_type": content_type,
        "accepted": len(entries),
        "written": written,
        "kafka_published": kafka_published,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }

    return {
        "accepted": len(entries),
        "written": written,
        "kafka_published": kafka_published,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }


@app.post("/ingest")
async def ingest_direct(request: Request) -> dict[str, Any]:
    event = await request.json()
    entries = event_to_journal_entries(event)
    written = 0
    kafka_published = 0
    active_adapters: dict[str, Any] = {}
    for name, adapter in adapters.items():
        if name == "druid" and not is_true("DRUID_DIRECT_WRITE_ENABLED", "false"):
            continue
        if name == "pinot" and not is_true("PINOT_DIRECT_WRITE_ENABLED", "false"):
            continue
        if await adapter.healthy():
            active_adapters[name] = adapter

    backend_writes: dict[str, int] = {name: 0 for name in active_adapters.keys()}
    backend_errors: dict[str, str] = {}
    for entry in entries:
        if publish_entry_to_kafka(entry):
            kafka_published += 1
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
        "kafka_published": kafka_published,
        "backend_writes": backend_writes,
        "backend_errors": backend_errors,
    }
