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
from confluent_kafka import Consumer, Producer
from fastapi import FastAPI, HTTPException, Request
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest

from storage_writer.adapters import ClickHouseAdapter, DruidAdapter, PinotAdapter
from storage_writer.master_data import load_accounts_by_code, load_accounts_by_role

app = FastAPI(title="synthetic-ledger-storage-writer", version="0.1.0")
last_otlp_stats: dict[str, Any] = {}
druid_supervisor_status: dict[str, Any] = {}
pinot_realtime_status: dict[str, Any] = {}
kafka_fanout_status: dict[str, Any] = {}
ACCOUNTS_BY_CODE = load_accounts_by_code()
ACCOUNTS_BY_ROLE = load_accounts_by_role()


def build_adapters() -> dict[str, Any]:
    registry = {
        "clickhouse": ClickHouseAdapter,
        "druid": DruidAdapter,
        "pinot": PinotAdapter,
    }
    enabled_csv = os.getenv("TARGET_BACKENDS") or os.getenv("ACTIVE_STACKS") or "clickhouse,druid,pinot"
    enabled = [item.strip() for item in enabled_csv.split(",") if item.strip()]
    return {name: registry[name]() for name in enabled if name in registry}


adapters = build_adapters()


def is_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def ledger_entries_topic() -> str:
    return os.getenv("LEDGER_ENTRIES_KAFKA_TOPIC", os.getenv("DRUID_KAFKA_TOPIC", "ledger-entries-v1"))


def direct_write_enabled(name: str) -> bool:
    if name == "clickhouse":
        default = "false" if is_true("KAFKA_FANOUT_CONSUMER_ENABLED", "true") else "true"
        return is_true("CLICKHOUSE_DIRECT_WRITE_ENABLED", default)
    if name == "druid":
        return is_true("DRUID_DIRECT_WRITE_ENABLED", "false")
    if name == "pinot":
        return is_true("PINOT_DIRECT_WRITE_ENABLED", "false")
    return False


def kafka_fanout_target_names() -> list[str]:
    configured = [item.strip() for item in os.getenv("KAFKA_FANOUT_TARGET_BACKENDS", "clickhouse").split(",") if item.strip()]
    return [name for name in configured if name in adapters]


def build_entries_kafka_producer() -> Producer | None:
    if not is_true("LEDGER_ENTRIES_KAFKA_PUBLISH_ENABLED", os.getenv("DRUID_KAFKA_PUBLISH_ENABLED", "true")):
        return None
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    return Producer({"bootstrap.servers": bootstrap, "linger.ms": 10, "batch.num.messages": 1000})


def build_entries_kafka_consumer() -> Consumer | None:
    if not is_true("KAFKA_FANOUT_CONSUMER_ENABLED", "true"):
        return None
    targets = kafka_fanout_target_names()
    if not targets:
        return None
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    group_id = os.getenv("KAFKA_FANOUT_GROUP_ID", "ledger-fanout-clickhouse-v1")
    offset_reset = os.getenv("KAFKA_FANOUT_AUTO_OFFSET_RESET", "latest")
    consumer = Consumer(
        {
            "bootstrap.servers": bootstrap,
            "group.id": group_id,
            "auto.offset.reset": offset_reset,
            "enable.auto.commit": False,
        }
    )
    consumer.subscribe([ledger_entries_topic()])
    return consumer


entries_kafka_producer = build_entries_kafka_producer()
entries_kafka_consumer = build_entries_kafka_consumer()


def publish_entry_to_kafka(entry: dict[str, Any]) -> bool:
    if entries_kafka_producer is None:
        return False
    topic = ledger_entries_topic()
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


async def consume_entries_from_kafka() -> None:
    global kafka_fanout_status
    if entries_kafka_consumer is None:
        kafka_fanout_status = {
            "enabled": False,
            "reason": "KAFKA_FANOUT_CONSUMER_ENABLED=false or no target backends configured",
        }
        return

    targets = kafka_fanout_target_names()
    kafka_fanout_status = {
        "enabled": True,
        "state": "starting",
        "topic": ledger_entries_topic(),
        "target_backends": targets,
        "messages_processed": 0,
        "backend_writes": {name: 0 for name in targets},
    }

    while True:
        try:
            message = await asyncio.to_thread(entries_kafka_consumer.poll, 1.0)
            if message is None:
                kafka_fanout_status["state"] = "idle"
                continue

            if message.error():
                kafka_fanout_status.update({"state": "error", "error": str(message.error())})
                await asyncio.sleep(1)
                continue

            payload = json.loads(message.value().decode("utf-8"))
            successful_targets: list[str] = []
            backend_errors: dict[str, str] = {}
            for name in targets:
                adapter = adapters.get(name)
                if adapter is None:
                    continue
                try:
                    await adapter.write_event(dict(payload))
                    successful_targets.append(name)
                    kafka_fanout_status["backend_writes"][name] = kafka_fanout_status["backend_writes"].get(name, 0) + 1
                except Exception as exc:
                    backend_errors[name] = str(exc)

            if len(successful_targets) != len(targets):
                kafka_fanout_status.update(
                    {
                        "state": "retrying",
                        "error": f"fanout failed for backends: {backend_errors}",
                        "last_backend_errors": backend_errors,
                    }
                )
                await asyncio.sleep(1)
                continue

            await asyncio.to_thread(entries_kafka_consumer.commit, message=message, asynchronous=False)
            kafka_fanout_status.update(
                {
                    "state": "running",
                    "messages_processed": kafka_fanout_status.get("messages_processed", 0) + 1,
                    "last_event_id": payload.get("event_id"),
                    "last_offsets": {
                        "topic": message.topic(),
                        "partition": message.partition(),
                        "offset": message.offset(),
                    },
                    "last_backend_errors": {},
                }
            )
        except Exception as exc:
            kafka_fanout_status.update({"state": "error", "error": str(exc)})
            await asyncio.sleep(1)


async def ensure_druid_kafka_supervisor() -> None:
    global druid_supervisor_status
    if not is_true("DRUID_KAFKA_CONSUMER_ENABLED", "true"):
        druid_supervisor_status = {"enabled": False, "reason": "DRUID_KAFKA_CONSUMER_ENABLED=false"}
        return

    if "druid" not in adapters:
        druid_supervisor_status = {"enabled": False, "reason": "druid adapter disabled"}
        return

    topic = ledger_entries_topic()
    datasource = os.getenv("DRUID_DATASOURCE", "ledger_events")
    druid_url = os.getenv("DRUID_OVERLORD_URL", "http://druid-overlord:8081")
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    use_earliest_offset = is_true("DRUID_KAFKA_USE_EARLIEST_OFFSET", "false")

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
                        "company_name",
                        "entry_side",
                        "account_code",
                        "account_name",
                        "account_role",
                        "statement_section",
                        "currency",
                        "ontology_event_type",
                        "ontology_description",
                        "ontology_source",
                        "product_id",
                        "product_name",
                        "product_category",
                        "product_brand",
                        "supplier_id",
                        "supplier_name",
                        "customer_id",
                        "customer_name",
                        "customer_cpf",
                        "customer_email",
                        "customer_segment",
                        "warehouse_id",
                        "warehouse_name",
                        "channel",
                        "channel_name",
                        "entry_category",
                        "sale_id",
                        "order_id",
                        "order_status",
                        "order_origin",
                        "payment_method",
                        "payment_installments",
                        "coupon_code",
                        "device_type",
                        "sales_region",
                        "freight_service",
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
                    {"type": "doubleSum", "name": "quantity", "fieldName": "quantity"},
                    {"type": "doubleSum", "name": "unit_price", "fieldName": "unit_price"},
                    {"type": "doubleSum", "name": "gross_amount", "fieldName": "gross_amount"},
                    {"type": "doubleSum", "name": "net_amount", "fieldName": "net_amount"},
                    {"type": "doubleSum", "name": "tax_amount", "fieldName": "tax_amount"},
                    {"type": "doubleSum", "name": "marketplace_fee_amount", "fieldName": "marketplace_fee_amount"},
                    {"type": "doubleSum", "name": "inventory_cost_total", "fieldName": "inventory_cost_total"},
                    {"type": "doubleSum", "name": "cart_quantity", "fieldName": "cart_quantity"},
                    {"type": "doubleSum", "name": "cart_gross_amount", "fieldName": "cart_gross_amount"},
                    {"type": "doubleSum", "name": "cart_discount", "fieldName": "cart_discount"},
                    {"type": "doubleSum", "name": "cart_net_amount", "fieldName": "cart_net_amount"},
                    {"type": "longMax", "name": "revision", "fieldName": "revision"},
                    {"type": "longMax", "name": "is_current", "fieldName": "is_current"},
                    {"type": "longMax", "name": "cart_items_count", "fieldName": "cart_items_count"},
                    {"type": "longMax", "name": "payment_installments", "fieldName": "payment_installments"},
                    {"type": "longMax", "name": "sale_line_index", "fieldName": "sale_line_index"},
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
                "useEarliestOffset": use_earliest_offset,
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
    topic = ledger_entries_topic()
    kafka_bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    offset_reset = os.getenv("PINOT_KAFKA_AUTO_OFFSET_RESET", "largest")

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
            {"name": "company_name", "dataType": "STRING"},
            {"name": "entry_side", "dataType": "STRING"},
            {"name": "account_code", "dataType": "STRING"},
            {"name": "account_name", "dataType": "STRING"},
            {"name": "account_role", "dataType": "STRING"},
            {"name": "statement_section", "dataType": "STRING"},
            {"name": "currency", "dataType": "STRING"},
            {"name": "ontology_event_type", "dataType": "STRING"},
            {"name": "ontology_description", "dataType": "STRING"},
            {"name": "ontology_source", "dataType": "STRING"},
            {"name": "product_id", "dataType": "STRING"},
            {"name": "product_name", "dataType": "STRING"},
            {"name": "product_category", "dataType": "STRING"},
            {"name": "product_brand", "dataType": "STRING"},
            {"name": "supplier_id", "dataType": "STRING"},
            {"name": "supplier_name", "dataType": "STRING"},
            {"name": "customer_id", "dataType": "STRING"},
            {"name": "customer_name", "dataType": "STRING"},
            {"name": "customer_cpf", "dataType": "STRING"},
            {"name": "customer_email", "dataType": "STRING"},
            {"name": "customer_segment", "dataType": "STRING"},
            {"name": "warehouse_id", "dataType": "STRING"},
            {"name": "warehouse_name", "dataType": "STRING"},
            {"name": "channel", "dataType": "STRING"},
            {"name": "channel_name", "dataType": "STRING"},
            {"name": "entry_category", "dataType": "STRING"},
            {"name": "sale_id", "dataType": "STRING"},
            {"name": "order_id", "dataType": "STRING"},
            {"name": "order_status", "dataType": "STRING"},
            {"name": "order_origin", "dataType": "STRING"},
            {"name": "payment_method", "dataType": "STRING"},
            {"name": "coupon_code", "dataType": "STRING"},
            {"name": "device_type", "dataType": "STRING"},
            {"name": "sales_region", "dataType": "STRING"},
            {"name": "freight_service", "dataType": "STRING"},
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
            {"name": "quantity", "dataType": "DOUBLE"},
            {"name": "unit_price", "dataType": "DOUBLE"},
            {"name": "gross_amount", "dataType": "DOUBLE"},
            {"name": "net_amount", "dataType": "DOUBLE"},
            {"name": "tax_amount", "dataType": "DOUBLE"},
            {"name": "marketplace_fee_amount", "dataType": "DOUBLE"},
            {"name": "inventory_cost_total", "dataType": "DOUBLE"},
            {"name": "cart_quantity", "dataType": "DOUBLE"},
            {"name": "cart_gross_amount", "dataType": "DOUBLE"},
            {"name": "cart_discount", "dataType": "DOUBLE"},
            {"name": "cart_net_amount", "dataType": "DOUBLE"},
            {"name": "is_current", "dataType": "INT"},
            {"name": "revision", "dataType": "INT"},
            {"name": "cart_items_count", "dataType": "INT"},
            {"name": "payment_installments", "dataType": "INT"},
            {"name": "sale_line_index", "dataType": "INT"},
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
                "stream.kafka.consumer.prop.auto.offset.reset": offset_reset,
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
                    desired_fields = {
                        item["name"]
                        for group in (
                            schema_payload["dimensionFieldSpecs"],
                            schema_payload["metricFieldSpecs"],
                            schema_payload["dateTimeFieldSpecs"],
                        )
                        for item in group
                    }
                    if not desired_fields.issubset(current_fields):
                        schema_update = await client.put(f"{controller_url}/schemas/{schema_name}", json=schema_payload)
                        schema_update.raise_for_status()

                tables_response = await client.get(f"{controller_url}/tables")
                tables_response.raise_for_status()
                existing_tables = set((tables_response.json() or {}).get("tables", []))
                has_realtime_table = realtime_table_name in existing_tables or table in existing_tables

                if not has_realtime_table:
                    table_create = await client.post(f"{controller_url}/tables", json=table_payload)
                    table_create.raise_for_status()
                else:
                    table_get = await client.get(f"{controller_url}/tables/{realtime_table_name}")
                    table_get.raise_for_status()
                    current_table = (table_get.json() or {}).get("REALTIME", {})
                    current_stream_config = ((current_table.get("tableIndexConfig") or {}).get("streamConfigs") or {})
                    desired_stream_config = table_payload["tableIndexConfig"]["streamConfigs"]
                    if any(current_stream_config.get(key) != value for key, value in desired_stream_config.items()):
                        table_update = await client.put(f"{controller_url}/tables/{realtime_table_name}", json=table_payload)
                        table_update.raise_for_status()

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
    account = ACCOUNTS_BY_CODE.get(account_code)
    if account:
        return str(account.get("account_name", account_code))
    if "-" in account_code:
        return account_code.split("-", maxsplit=1)[1]
    return account_code


def statement_section(account_code: str) -> str:
    account = ACCOUNTS_BY_CODE.get(account_code)
    if account:
        return str(account.get("statement_section", "other"))
    if account_code.startswith("1."):
        return "asset"
    if account_code.startswith("2."):
        return "liability"
    if account_code.startswith("3."):
        return "revenue"
    if account_code.startswith("4."):
        return "expense"
    return "other"


def account_role(account_code: str) -> str:
    account = ACCOUNTS_BY_CODE.get(account_code)
    if account:
        return str(account.get("account_role", "other"))
    return "other"


def entry_category(account_code: str, event_type: str) -> str:
    account = ACCOUNTS_BY_CODE.get(account_code)
    if account:
        return str(account.get("entry_category", "operacional"))
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


def account_code_for_role(role: str) -> str:
    account = ACCOUNTS_BY_ROLE.get(role)
    if not account:
        raise KeyError(f"Account role not configured: {role}")
    return str(account["account_code"])


def optional_text(value: Any) -> str | None:
    if value in (None, "", "null", "None"):
        return None
    return str(value)


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
    role = account_role(account_code)
    sign = 1.0 if entry_side == "debit" else -1.0
    occurred_at = event.get("occurred_at", now_iso())
    ingested_at = event.get("ingested_at", now_iso())
    canonical_event_type = str(event.get("event_type", "unknown"))
    product_id = str(event.get("product_id", "unknown-product"))
    supplier_id = optional_text(event.get("supplier_id"))
    supplier_name = optional_text(event.get("supplier_name"))
    customer_id = optional_text(event.get("customer_id"))
    customer_name = optional_text(event.get("customer_name"))
    customer_cpf = optional_text(event.get("customer_cpf"))
    customer_email = optional_text(event.get("customer_email"))
    customer_segment = optional_text(event.get("customer_segment"))
    warehouse_id = str(event.get("warehouse_id", "unknown-warehouse"))
    warehouse_name = str(event.get("warehouse_name", warehouse_id))
    channel = str(event.get("channel", "unknown-channel"))
    channel_name = str(event.get("channel_name", channel))

    return {
        "entry_id": str(uuid.uuid4()),
        "event_id": event["event_id"],
        "trace_id": event["event_id"],
        "company_id": event["company_id"],
        "tenant_id": event["tenant_id"],
        "company_name": event.get("company_name", event["company_id"]),
        "entry_side": entry_side,
        "account_code": account_code,
        "account_name": account_name(account_code),
        "account_role": role,
        "statement_section": section,
        "amount": round(amount, 2),
        "signed_amount": round(amount * sign, 2),
        "quantity": round(float(event.get("quantity", 0.0) or 0.0), 3),
        "unit_price": round(float(event.get("unit_price", 0.0) or 0.0), 2),
        "gross_amount": round(float(event.get("gross_amount", 0.0) or 0.0), 2),
        "net_amount": round(float(event.get("net_amount", 0.0) or 0.0), 2),
        "tax_amount": round(float(event.get("tax", 0.0) or 0.0), 2),
        "marketplace_fee_amount": round(float(event.get("marketplace_fee", 0.0) or 0.0), 2),
        "inventory_cost_total": round(float(event.get("cmv", 0.0) or 0.0), 2),
        "currency": event.get("currency", "BRL"),
        "ontology_event_type": canonical_event_type,
        "ontology_description": ontology_description,
        "ontology_source": ontology_source,
        "product_id": product_id,
        "product_name": str(event.get("product_name", product_id)),
        "product_category": str(event.get("product_category", "Sem categoria")),
        "product_brand": str(event.get("product_brand", "Marca propria")),
        "supplier_id": supplier_id,
        "supplier_name": supplier_name,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "customer_cpf": customer_cpf,
        "customer_email": customer_email,
        "customer_segment": customer_segment,
        "warehouse_id": warehouse_id,
        "warehouse_name": warehouse_name,
        "channel": channel,
        "channel_name": channel_name,
        "entry_category": entry_category(account_code, canonical_event_type),
        "sale_id": optional_text(event.get("sale_id")),
        "order_id": str(event.get("order_id", event["event_id"])),
        "order_status": optional_text(event.get("order_status")),
        "order_origin": optional_text(event.get("order_origin")),
        "payment_method": optional_text(event.get("payment_method")),
        "payment_installments": int(event.get("payment_installments", 1) or 1),
        "coupon_code": optional_text(event.get("coupon_code")),
        "device_type": optional_text(event.get("device_type")),
        "sales_region": optional_text(event.get("sales_region")),
        "freight_service": optional_text(event.get("freight_service")),
        "cart_items_count": int(event.get("cart_items_count", 1) or 1),
        "cart_quantity": round(float(event.get("cart_quantity", event.get("quantity", 0.0)) or 0.0), 3),
        "cart_gross_amount": round(float(event.get("cart_gross_amount", event.get("gross_amount", 0.0)) or 0.0), 2),
        "cart_discount": round(float(event.get("cart_discount", event.get("discount", 0.0)) or 0.0), 2),
        "cart_net_amount": round(float(event.get("cart_net_amount", event.get("net_amount", 0.0)) or 0.0), 2),
        "sale_line_index": int(event.get("sale_line_index", 1) or 1),
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
    gross = round(float(event.get("gross_amount", 0.0) or 0.0), 2)
    discount = round(float(event.get("discount", 0.0) or 0.0), 2)
    net_amount = round(float(event.get("net_amount", max(gross - discount, 0.0)) or 0.0), 2)
    tax_amount = round(float(event.get("tax", 0.0) or 0.0), 2)
    marketplace_fee = round(float(event.get("marketplace_fee", 0.0) or 0.0), 2)
    cmv = round(float(event.get("cmv", 0.0) or 0.0), 2)

    canonical_event = {
        **event,
        "occurred_at": event.get("occurred_at", now_iso()),
        "ingested_at": event.get("ingested_at", now_iso()),
    }
    payload_hash = hashlib.sha256(json.dumps(canonical_event, sort_keys=True).encode("utf-8")).hexdigest()

    event_type = canonical_event.get("event_type")
    if event_type == "purchase":
        entries = [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code=account_code_for_role("inventory"),
                amount=net_amount,
                ontology_description="Entrada de mercadorias no estoque com base no pedido de compra.",
                payload_hash=payload_hash,
            ),
        ]
        if tax_amount > 0:
            entries.append(
                make_entry(
                    event=canonical_event,
                    entry_side="debit",
                    account_code=account_code_for_role("recoverable_tax"),
                    amount=tax_amount,
                    ontology_description="Reconhecimento de tributos recuperaveis sobre a compra.",
                    payload_hash=payload_hash,
                )
            )
        entries.append(
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code=account_code_for_role("accounts_payable"),
                amount=round(net_amount + tax_amount, 2),
                ontology_description="Reconhecimento do passivo com fornecedor pela compra recebida.",
                payload_hash=payload_hash,
            )
        )
        return entries

    if event_type == "supplier_payment":
        payable_account_code = str(canonical_event.get("debit_account", account_code_for_role("accounts_payable")))
        settlement_account_code = str(canonical_event.get("credit_account", account_code_for_role("bank_accounts")))
        return [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code=payable_account_code,
                amount=net_amount,
                ontology_description="Liquidacao parcial ou total do passivo com fornecedor referente a compras recebidas.",
                payload_hash=payload_hash,
            ),
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code=settlement_account_code,
                amount=net_amount,
                ontology_description="Baixa financeira da obrigacao com fornecedor usando caixa ou bancos.",
                payload_hash=payload_hash,
            ),
        ]

    if event_type == "sale":
        settlement_account_code = str(canonical_event.get("debit_account", account_code_for_role("cash")))
        settlement_amount = round(net_amount + tax_amount - marketplace_fee, 2)
        entries = [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code=settlement_account_code,
                amount=max(settlement_amount, 0.0),
                ontology_description="Liquidacao financeira liquida da venda no canal selecionado.",
                payload_hash=payload_hash,
            ),
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code=account_code_for_role("revenue"),
                amount=net_amount,
                ontology_description="Reconhecimento da receita operacional liquida de descontos comerciais.",
                payload_hash=payload_hash,
            ),
        ]
        if marketplace_fee > 0:
            entries.append(
                make_entry(
                    event=canonical_event,
                    entry_side="debit",
                    account_code=account_code_for_role("marketplace_fees"),
                    amount=marketplace_fee,
                    ontology_description="Despesa comercial cobrada pelo canal de venda.",
                    payload_hash=payload_hash,
                )
            )
        if tax_amount > 0:
            entries.append(
                make_entry(
                    event=canonical_event,
                    entry_side="credit",
                    account_code=account_code_for_role("tax_payable"),
                    amount=tax_amount,
                    ontology_description="Tributos sobre vendas a recolher derivados do documento fiscal.",
                    payload_hash=payload_hash,
                )
            )
        if cmv > 0:
            entries.extend(
                [
                    make_entry(
                        event=canonical_event,
                        entry_side="debit",
                        account_code=account_code_for_role("cogs"),
                        amount=cmv,
                        ontology_description="Reconhecimento do custo da mercadoria vendida.",
                        payload_hash=payload_hash,
                    ),
                    make_entry(
                        event=canonical_event,
                        entry_side="credit",
                        account_code=account_code_for_role("inventory"),
                        amount=cmv,
                        ontology_description="Baixa de estoque por venda.",
                        payload_hash=payload_hash,
                    ),
                ]
            )
        return entries

    if event_type == "return":
        refund_account_code = str(canonical_event.get("credit_account", account_code_for_role("cash")))
        entries = [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code=account_code_for_role("returns"),
                amount=net_amount,
                ontology_description="Reconhecimento da devolucao do cliente reduzindo a receita liquida.",
                payload_hash=payload_hash,
            ),
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code=refund_account_code,
                amount=round(net_amount + tax_amount, 2),
                ontology_description="Estorno financeiro do valor devolvido ao cliente.",
                payload_hash=payload_hash,
            ),
        ]
        if tax_amount > 0:
            entries.append(
                make_entry(
                    event=canonical_event,
                    entry_side="debit",
                    account_code=account_code_for_role("tax_payable"),
                    amount=tax_amount,
                    ontology_description="Reversao dos tributos sobre venda associados ao item devolvido.",
                    payload_hash=payload_hash,
                )
            )
        if cmv > 0:
            entries.extend(
                [
                    make_entry(
                        event=canonical_event,
                        entry_side="debit",
                        account_code=account_code_for_role("inventory"),
                        amount=cmv,
                        ontology_description="Retorno da mercadoria devolvida ao estoque disponivel.",
                        payload_hash=payload_hash,
                    ),
                    make_entry(
                        event=canonical_event,
                        entry_side="credit",
                        account_code=account_code_for_role("cogs"),
                        amount=cmv,
                        ontology_description="Reversao do custo da mercadoria vendida para item devolvido.",
                        payload_hash=payload_hash,
                    ),
                ]
            )
        return entries

    if event_type == "freight":
        freight_account_code = str(canonical_event.get("debit_account", account_code_for_role("outbound_freight")))
        settlement_account_code = str(canonical_event.get("credit_account", account_code_for_role("bank_accounts")))
        entries = [
            make_entry(
                event=canonical_event,
                entry_side="debit",
                account_code=freight_account_code,
                amount=net_amount,
                ontology_description="Reconhecimento do frete de expedicao vinculado ao pedido faturado.",
                payload_hash=payload_hash,
            )
        ]
        if marketplace_fee > 0:
            entries.append(
                make_entry(
                    event=canonical_event,
                    entry_side="debit",
                    account_code=account_code_for_role("bank_fees"),
                    amount=marketplace_fee,
                    ontology_description="Tarifa bancaria cobrada na liquidacao do frete operacional.",
                    payload_hash=payload_hash,
                )
            )
        entries.append(
            make_entry(
                event=canonical_event,
                entry_side="credit",
                account_code=settlement_account_code,
                amount=round(net_amount + marketplace_fee, 2),
                ontology_description="Baixa financeira do frete pago ao operador logistico.",
                payload_hash=payload_hash,
            )
        )
        return entries

    return [
        make_entry(
            event=canonical_event,
            entry_side="debit",
                account_code=str(canonical_event.get("debit_account", account_code_for_role("cash"))),
                amount=net_amount,
            ontology_description="Lançamento de débito derivado de evento canônico.",
            payload_hash=payload_hash,
        ),
        make_entry(
            event=canonical_event,
            entry_side="credit",
                account_code=str(canonical_event.get("credit_account", account_code_for_role("revenue"))),
                amount=net_amount,
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


@app.get("/debug/kafka-fanout")
async def debug_kafka_fanout() -> dict[str, Any]:
    return kafka_fanout_status


@app.on_event("startup")
async def startup_tasks() -> None:
    asyncio.create_task(bootstrap_druid_supervisor_task())
    asyncio.create_task(bootstrap_pinot_realtime_task())
    asyncio.create_task(consume_entries_from_kafka())


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
        if not direct_write_enabled(name):
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
        raise HTTPException(status_code=503, detail="No direct backend or kafka topic available for write")

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
        if not direct_write_enabled(name):
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
