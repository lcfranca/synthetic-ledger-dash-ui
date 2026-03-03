import os
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastavro import parse_schema
from fastavro.validation import validate
from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import ExportLogsServiceRequest
import orjson
from confluent_kafka import Producer
from pydantic import BaseModel, Field


class AccountingEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "1.0.0"
    event_type: str
    company_id: str
    tenant_id: str
    occurred_at: str
    ingested_at: str
    product_id: str
    supplier_id: str | None = None
    customer_id: str | None = None
    warehouse_id: str
    quantity: float
    unit_price: float
    discount: float
    tax: float
    currency: str = "BRL"
    cost_basis: float
    cmv: float
    debit_account: str
    credit_account: str
    channel: str = "online"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def random_event(company_id: str) -> AccountingEvent:
    event_type = random.choice(["purchase", "sale"])
    quantity = round(random.uniform(1, 10), 2)
    unit_price = round(random.uniform(10, 500), 2)
    gross = quantity * unit_price
    discount = round(gross * random.uniform(0, 0.08), 2)
    tax = round((gross - discount) * random.uniform(0.04, 0.18), 2)
    cost_basis = round(gross * random.uniform(0.5, 0.9), 2)
    cmv = cost_basis if event_type == "sale" else 0.0

    if event_type == "purchase":
        debit, credit = "1.1.03.01-Estoque", "1.1.01.01-Caixa"
    else:
        debit, credit = "1.1.01.01-Caixa", "3.1.01.01-Receita"

    return AccountingEvent(
        event_type=event_type,
        company_id=company_id,
        tenant_id=f"tenant-{company_id}",
        occurred_at=now_iso(),
        ingested_at=now_iso(),
        product_id=f"sku-{random.randint(1, 200)}",
        supplier_id=f"sup-{random.randint(1, 50)}" if event_type == "purchase" else None,
        customer_id=f"cus-{random.randint(1, 500)}" if event_type == "sale" else None,
        warehouse_id=f"wh-{random.randint(1, 4)}",
        quantity=quantity,
        unit_price=unit_price,
        discount=discount,
        tax=tax,
        cost_basis=cost_basis,
        cmv=cmv,
        debit_account=debit,
        credit_account=credit,
    )


def delivery_report(err, msg):
    if err is not None:
        print(f"delivery failed: {err}")


def load_avro_schema(version: str) -> dict:
    schema_path = Path(__file__).resolve().parent / "schemas" / f"accounting_event_v{version}.avsc"
    return parse_schema(orjson.loads(schema_path.read_bytes()))


def build_otlp_log_payload(event_payload: dict) -> bytes:
    request = ExportLogsServiceRequest()
    resource_log = request.resource_logs.add()
    service_name = resource_log.resource.attributes.add()
    service_name.key = "service.name"
    service_name.value.string_value = "synthetic-ledger-producer"

    scope_log = resource_log.scope_logs.add()
    scope_log.scope.name = "synthetic-ledger-producer"
    scope_log.scope.version = "0.1.0"

    log_record = scope_log.log_records.add()
    now_nanos = int(time.time_ns())
    log_record.time_unix_nano = now_nanos
    log_record.observed_time_unix_nano = now_nanos
    log_record.body.string_value = orjson.dumps(event_payload).decode("utf-8")

    return request.SerializeToString()


def main() -> None:
    bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092")
    topic = os.getenv("KAFKA_TOPIC", "accounting-events-v1")
    schema_major_version = os.getenv("SCHEMA_MAJOR_VERSION", "1")
    events_per_second = float(os.getenv("PRODUCER_EVENTS_PER_SECOND", "100"))
    company_id = os.getenv("PRODUCER_COMPANY_ID", "company-demo")
    avro_schema = load_avro_schema(schema_major_version)

    producer = Producer({"bootstrap.servers": bootstrap_servers, "linger.ms": 5, "batch.num.messages": 1000})
    sleep_interval = 1.0 / max(events_per_second, 1.0)

    print(f"producer started topic={topic} eps={events_per_second} schema=v{schema_major_version}")
    while True:
        event = random_event(company_id)
        event_payload = event.model_dump()
        if not validate(event_payload, avro_schema):
            print("event rejected by avro validation")
            continue

        payload = build_otlp_log_payload(event_payload)
        producer.produce(topic=topic, key=event.company_id, value=payload, callback=delivery_report)
        producer.poll(0)
        time.sleep(sleep_interval)


if __name__ == "__main__":
    main()
