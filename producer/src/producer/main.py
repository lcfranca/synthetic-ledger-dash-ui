import os
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

from producer.domain import Catalog, RetailSimulation


class AccountingEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    schema_version: str = "1.2.0"
    event_type: str
    company_id: str
    tenant_id: str
    company_name: str
    occurred_at: str
    ingested_at: str
    product_id: str
    product_name: str
    product_category: str
    product_brand: str
    supplier_id: str | None = None
    supplier_name: str | None = None
    customer_id: str | None = None
    customer_name: str | None = None
    customer_cpf: str | None = None
    customer_email: str | None = None
    customer_segment: str | None = None
    warehouse_id: str
    warehouse_name: str
    quantity: float
    unit_price: float
    gross_amount: float
    discount: float
    net_amount: float
    tax: float
    marketplace_fee: float
    currency: str = "BRL"
    cost_basis: float
    cmv: float
    debit_account: str
    credit_account: str
    channel: str
    channel_name: str
    sale_id: str | None = None
    order_id: str
    order_status: str | None = None
    order_origin: str | None = None
    payment_method: str | None = None
    payment_installments: int = 1
    coupon_code: str | None = None
    device_type: str | None = None
    sales_region: str | None = None
    freight_service: str | None = None
    cart_items_count: int = 1
    cart_quantity: float = 0.0
    cart_gross_amount: float = 0.0
    cart_discount: float = 0.0
    cart_net_amount: float = 0.0
    sale_line_index: int = 1


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_event_from_scenario(catalog: Catalog, company_id: str, scenario: dict) -> AccountingEvent:
    product = scenario["product"]
    supplier = scenario["supplier"]
    warehouse = scenario["warehouse"]
    channel = scenario["channel"]
    occurred_at = now_iso()

    debit = str(scenario.get("debit_account", "1.1.01.01"))
    credit = str(scenario.get("credit_account", "3.1.01.01"))

    return AccountingEvent(
        event_type=scenario["event_type"],
        company_id=company_id,
        tenant_id=catalog.company["tenant_id"],
        company_name=catalog.company["trade_name"],
        occurred_at=occurred_at,
        ingested_at=now_iso(),
        product_id=product.product_id,
        product_name=product.product_name,
        product_category=product.product_category,
        product_brand=product.product_brand,
        supplier_id=supplier.supplier_id if scenario["event_type"] == "purchase" else None,
        supplier_name=supplier.supplier_name if scenario["event_type"] == "purchase" else None,
        customer_id=scenario["customer_id"],
        customer_name=scenario.get("customer_name"),
        customer_cpf=scenario.get("customer_cpf"),
        customer_email=scenario.get("customer_email"),
        customer_segment=scenario.get("customer_segment"),
        warehouse_id=warehouse.warehouse_id,
        warehouse_name=warehouse.warehouse_name,
        quantity=scenario["quantity"],
        unit_price=scenario["unit_price"],
        gross_amount=scenario["gross_amount"],
        discount=scenario["discount"],
        net_amount=scenario["net_amount"],
        tax=scenario["tax"],
        marketplace_fee=scenario["marketplace_fee"],
        cost_basis=scenario["cost_basis"],
        cmv=scenario["cmv"],
        debit_account=debit,
        credit_account=credit,
        channel=channel.channel_id,
        channel_name=channel.channel_name,
        sale_id=scenario.get("sale_id"),
        order_id=str(scenario.get("order_id", f"{scenario['event_type'][:2].upper()}-{uuid.uuid4().hex[:12]}")),
        order_status=scenario.get("order_status"),
        order_origin=scenario.get("order_origin"),
        payment_method=scenario.get("payment_method"),
        payment_installments=int(scenario.get("payment_installments", 1) or 1),
        coupon_code=scenario.get("coupon_code"),
        device_type=scenario.get("device_type"),
        sales_region=scenario.get("sales_region"),
        freight_service=scenario.get("freight_service"),
        cart_items_count=int(scenario.get("cart_items_count", 1) or 1),
        cart_quantity=float(scenario.get("cart_quantity", scenario.get("quantity", 0.0)) or 0.0),
        cart_gross_amount=float(scenario.get("cart_gross_amount", scenario.get("gross_amount", 0.0)) or 0.0),
        cart_discount=float(scenario.get("cart_discount", scenario.get("discount", 0.0)) or 0.0),
        cart_net_amount=float(scenario.get("cart_net_amount", scenario.get("net_amount", 0.0)) or 0.0),
        sale_line_index=int(scenario.get("sale_line_index", 1) or 1),
    )


def build_event(simulation: RetailSimulation, catalog: Catalog, company_id: str) -> AccountingEvent:
    return build_event_from_scenario(catalog, company_id, simulation.next_event())


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
    catalog = Catalog()
    simulation = RetailSimulation(catalog)

    producer = Producer({"bootstrap.servers": bootstrap_servers, "linger.ms": 5, "batch.num.messages": 1000})
    sleep_interval = 1.0 / max(events_per_second, 1.0)

    print(f"producer started topic={topic} eps={events_per_second} schema=v{schema_major_version}")
    bootstrap_events = simulation.drain_bootstrap_events()
    for scenario in bootstrap_events:
        event = build_event_from_scenario(catalog, company_id, scenario)
        event_payload = event.model_dump()
        if not validate(event_payload, avro_schema):
            print(f"bootstrap event rejected by avro validation product={event.product_id}")
            continue
        payload = build_otlp_log_payload(event_payload)
        producer.produce(topic=topic, key=event.company_id, value=payload, callback=delivery_report)
        producer.poll(0)
    if bootstrap_events:
        producer.flush(5)
        print(f"bootstrap inventory events published={len(bootstrap_events)}")
    while True:
        event = build_event(simulation, catalog, company_id)
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
