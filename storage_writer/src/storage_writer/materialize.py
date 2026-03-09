import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row


def _split_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


def _is_true(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


class MaterializeBootstrapper:
    def __init__(self) -> None:
        self.enabled = _is_true("MATERIALIZE_ENABLED", "true")
        self.conninfo = os.getenv("MATERIALIZE_URL", "postgresql://materialize@materialized:6875/materialize")
        self.schema = os.getenv("MATERIALIZE_VIEW_SCHEMA", os.getenv("MATERIALIZE_SCHEMA", "public"))
        self.kafka_broker = os.getenv("MATERIALIZE_KAFKA_BROKER", os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:9092"))
        self.kafka_topic = os.getenv("MATERIALIZE_KAFKA_TOPIC", os.getenv("LEDGER_ENTRIES_KAFKA_TOPIC", "ledger-entries-v1"))
        self.group_id_prefix = os.getenv("MATERIALIZE_KAFKA_GROUP_ID_PREFIX", "ledger-materialize")
        self.retry_seconds = max(int(os.getenv("MATERIALIZE_BOOTSTRAP_RETRY_SECONDS", "5") or 5), 1)
        self.max_attempts = max(int(os.getenv("MATERIALIZE_BOOTSTRAP_MAX_ATTEMPTS", "0") or 0), 0)
        self.start_timestamp_ms = (os.getenv("MATERIALIZE_BOOTSTRAP_START_TIMESTAMP_MS") or "").strip()
        self.expected_view_lag_ms = max(int(os.getenv("MATERIALIZE_EXPECTED_VIEW_LAG_MS", "2000") or 2000), 0)
        self.expected_freshness_ms = max(int(os.getenv("MATERIALIZE_EXPECTED_FRESHNESS_MS", "5000") or 5000), 0)
        self.target_hydration_rows = max(int(os.getenv("MATERIALIZE_TARGET_HYDRATION_ROWS", "1") or 1), 0)
        self.status: dict[str, Any] = {
            "enabled": self.enabled,
            "state": "disabled" if not self.enabled else "idle",
            "schema": self.schema,
            "topic": self.kafka_topic,
            "group_id_prefix": self.group_id_prefix,
            "objects": self._object_names(),
        }

    def _object_names(self) -> dict[str, str]:
        prefix = f"{self.schema}."
        return {
            "connection": f"{prefix}ledger_kafka_connection",
            "source": f"{prefix}ledger_entries_source",
            "progress": f"{prefix}ledger_entries_source_progress",
            "typed_view": f"{prefix}ledger_entries_typed",
            "entries_view": f"{prefix}ledger_entries_current_mv",
            "summary_view": f"{prefix}ledger_summary_by_role_mv",
            "sales_view": f"{prefix}ledger_sales_mv",
            "account_balances_view": f"{prefix}ledger_account_balances_mv",
            "product_metrics_view": f"{prefix}ledger_product_metrics_mv",
        }

    def _runtime_enabled(self) -> bool:
        if not self.enabled:
            return False
        configured = _split_csv(os.getenv("ACTIVE_STACKS")) | _split_csv(os.getenv("TARGET_BACKENDS"))
        if not configured:
            return True
        return "materialize" in configured

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.conninfo, autocommit=True, row_factory=dict_row)

    @staticmethod
    def _json_text(field: str) -> str:
        return f"NULLIF(NULLIF(data->>'{field}', ''), 'null')"

    def _typed_view_statement(self) -> str:
        objects = self._object_names()
        text = self._json_text
        return f"""
        CREATE VIEW IF NOT EXISTS {objects['typed_view']} AS
        SELECT
            COALESCE({text('entry_id')}, '') AS entry_id,
            COALESCE({text('event_id')}, '') AS event_id,
            COALESCE({text('trace_id')}, '') AS trace_id,
            COALESCE({text('company_id')}, '') AS company_id,
            COALESCE({text('tenant_id')}, '') AS tenant_id,
            COALESCE({text('company_name')}, '') AS company_name,
            COALESCE({text('entry_side')}, '') AS entry_side,
            COALESCE({text('account_code')}, '') AS account_code,
            COALESCE({text('account_name')}, '') AS account_name,
            COALESCE({text('account_role')}, '') AS account_role,
            COALESCE({text('statement_section')}, '') AS statement_section,
            COALESCE(({text('amount')})::double precision, 0.0) AS amount,
            COALESCE(({text('signed_amount')})::double precision, 0.0) AS signed_amount,
            COALESCE(({text('quantity')})::double precision, 0.0) AS quantity,
            COALESCE(({text('unit_price')})::double precision, 0.0) AS unit_price,
            COALESCE(({text('gross_amount')})::double precision, 0.0) AS gross_amount,
            COALESCE(({text('net_amount')})::double precision, 0.0) AS net_amount,
            COALESCE(({text('tax_amount')})::double precision, 0.0) AS tax_amount,
            COALESCE(({text('marketplace_fee_amount')})::double precision, 0.0) AS marketplace_fee_amount,
            COALESCE(({text('inventory_cost_total')})::double precision, 0.0) AS inventory_cost_total,
            COALESCE({text('currency')}, 'BRL') AS currency,
            COALESCE({text('ontology_event_type')}, '') AS ontology_event_type,
            COALESCE({text('ontology_description')}, '') AS ontology_description,
            COALESCE({text('ontology_source')}, '') AS ontology_source,
            COALESCE({text('product_id')}, '') AS product_id,
            COALESCE({text('product_name')}, '') AS product_name,
            COALESCE({text('product_category')}, '') AS product_category,
            COALESCE({text('product_brand')}, '') AS product_brand,
            {text('supplier_id')} AS supplier_id,
            {text('supplier_name')} AS supplier_name,
            {text('customer_id')} AS customer_id,
            {text('customer_name')} AS customer_name,
            {text('customer_cpf')} AS customer_cpf,
            {text('customer_email')} AS customer_email,
            {text('customer_segment')} AS customer_segment,
            COALESCE({text('warehouse_id')}, '') AS warehouse_id,
            COALESCE({text('warehouse_name')}, '') AS warehouse_name,
            COALESCE({text('channel')}, COALESCE({text('channel_name')}, '')) AS channel,
            COALESCE({text('channel_name')}, COALESCE({text('channel')}, '')) AS channel_name,
            COALESCE({text('entry_category')}, '') AS entry_category,
            {text('sale_id')} AS sale_id,
            COALESCE({text('order_id')}, '') AS order_id,
            {text('order_status')} AS order_status,
            {text('order_origin')} AS order_origin,
            {text('payment_method')} AS payment_method,
            COALESCE(({text('payment_installments')})::integer, 1) AS payment_installments,
            {text('coupon_code')} AS coupon_code,
            {text('device_type')} AS device_type,
            {text('sales_region')} AS sales_region,
            {text('freight_service')} AS freight_service,
            COALESCE(({text('cart_items_count')})::integer, 0) AS cart_items_count,
            COALESCE(({text('cart_quantity')})::double precision, 0.0) AS cart_quantity,
            COALESCE(({text('cart_gross_amount')})::double precision, 0.0) AS cart_gross_amount,
            COALESCE(({text('cart_discount')})::double precision, 0.0) AS cart_discount,
            COALESCE(({text('cart_net_amount')})::double precision, 0.0) AS cart_net_amount,
            COALESCE(({text('sale_line_index')})::integer, 0) AS sale_line_index,
            COALESCE({text('source_payload_hash')}, '') AS source_payload_hash,
            COALESCE(({text('occurred_at')})::timestamptz, kafka_timestamp) AS occurred_at,
            COALESCE(({text('ingested_at')})::timestamptz, kafka_timestamp) AS ingested_at,
            COALESCE(({text('valid_from')})::timestamptz, kafka_timestamp) AS valid_from,
            ({text('valid_to')})::timestamptz AS valid_to,
            COALESCE(({text('is_current')})::integer, 0) AS is_current,
            COALESCE(({text('revision')})::integer, 1) AS revision,
            kafka_partition,
            kafka_offset,
            kafka_timestamp
        FROM {objects['source']}
        """.strip()

    def _bootstrap_statements(self) -> list[str]:
        objects = self._object_names()
        start_timestamp_clause = ""
        if self.start_timestamp_ms:
            start_timestamp_clause = f", START TIMESTAMP {int(self.start_timestamp_ms)}"
        return [
            f"CREATE SCHEMA IF NOT EXISTS {self.schema}",
            f"CREATE CONNECTION IF NOT EXISTS {objects['connection']} TO KAFKA (BROKER '{self.kafka_broker}', SECURITY PROTOCOL = 'PLAINTEXT')",
            (
                f"CREATE SOURCE IF NOT EXISTS {objects['source']} "
                f"FROM KAFKA CONNECTION {objects['connection']} (TOPIC '{self.kafka_topic}', GROUP ID PREFIX '{self.group_id_prefix}'{start_timestamp_clause}) "
                f"FORMAT JSON INCLUDE PARTITION AS kafka_partition, OFFSET AS kafka_offset, TIMESTAMP AS kafka_timestamp "
                f"EXPOSE PROGRESS AS {objects['progress']}"
            ),
            self._typed_view_statement(),
            (
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {objects['entries_view']} AS "
                f"SELECT * FROM {objects['typed_view']} WHERE is_current = 1"
            ),
            (
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {objects['summary_view']} AS "
                f"SELECT account_role, statement_section, SUM(signed_amount) AS signed_amount, COUNT(*) AS entry_count "
                f"FROM {objects['entries_view']} GROUP BY account_role, statement_section"
            ),
            (
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {objects['sales_view']} AS "
                f"SELECT "
                f"sale_id, "
                f"MAX(order_id) AS order_id, "
                f"MAX(occurred_at) AS occurred_at, "
                f"MAX(customer_id) AS customer_id, "
                f"MAX(customer_name) AS customer_name, "
                f"MAX(customer_cpf) AS customer_cpf, "
                f"MAX(customer_email) AS customer_email, "
                f"MAX(customer_segment) AS customer_segment, "
                f"MAX(channel) AS channel, "
                f"MAX(channel_name) AS channel_name, "
                f"MAX(payment_method) AS payment_method, "
                f"MAX(payment_installments) AS payment_installments, "
                f"MAX(order_status) AS order_status, "
                f"MAX(order_origin) AS order_origin, "
                f"MAX(coupon_code) AS coupon_code, "
                f"MAX(device_type) AS device_type, "
                f"MAX(sales_region) AS sales_region, "
                f"MAX(freight_service) AS freight_service, "
                f"MAX(product_name) AS lead_product, "
                f"COUNT(DISTINCT product_id) AS product_mix, "
                f"MAX(cart_items_count) AS cart_items_count, "
                f"SUM(quantity) AS quantity, "
                f"SUM(gross_amount) AS gross_amount, "
                f"SUM(net_amount) AS net_amount, "
                f"MAX(cart_discount) AS cart_discount, "
                f"SUM(tax_amount) AS tax_amount, "
                f"SUM(marketplace_fee_amount) AS marketplace_fee_amount, "
                f"SUM(inventory_cost_total) AS cmv "
                f"FROM {objects['entries_view']} "
                f"WHERE ontology_event_type = 'sale' AND account_role = 'revenue' AND sale_id IS NOT NULL AND sale_id <> '' "
                f"GROUP BY sale_id"
            ),
            (
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {objects['account_balances_view']} AS "
                f"SELECT account_code, SUM(signed_amount) AS current_balance, COUNT(*) AS entry_count "
                f"FROM {objects['entries_view']} GROUP BY account_code"
            ),
            (
                f"CREATE MATERIALIZED VIEW IF NOT EXISTS {objects['product_metrics_view']} AS "
                f"SELECT "
                f"product_id, "
                f"SUM(CASE WHEN account_role = 'inventory' AND (order_id = '' OR order_id NOT LIKE 'BOOT-%') THEN CASE WHEN entry_side = 'debit' THEN quantity ELSE 0.0 - quantity END ELSE 0.0 END) AS stock_delta_quantity, "
                f"SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN quantity ELSE 0.0 END) AS sold_quantity, "
                f"SUM(CASE WHEN ontology_event_type = 'return' AND account_role = 'inventory' THEN quantity ELSE 0.0 END) AS returned_quantity, "
                f"SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0.0 END) AS revenue_amount, "
                f"SUM(CASE WHEN account_role = 'returns' THEN amount ELSE 0.0 END) AS return_amount, "
                f"SUM(CASE WHEN account_role = 'cogs' THEN signed_amount ELSE 0.0 END) AS cogs_amount, "
                f"SUM(CASE WHEN account_role = 'marketplace_fees' THEN signed_amount ELSE 0.0 END) AS marketplace_fees_amount, "
                f"SUM(CASE WHEN account_role = 'outbound_freight' THEN signed_amount ELSE 0.0 END) AS freight_out_amount, "
                f"SUM(CASE WHEN account_role = 'bank_fees' THEN signed_amount ELSE 0.0 END) AS bank_fees_amount, "
                f"AVG(CASE WHEN ontology_event_type = 'purchase' AND account_role = 'inventory' AND unit_price > 0 THEN unit_price ELSE NULL END) AS average_purchase_price, "
                f"AVG(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' AND unit_price > 0 THEN unit_price ELSE NULL END) AS average_sale_price "
                f"FROM {objects['entries_view']} "
                f"WHERE product_id IS NOT NULL AND product_id <> '' "
                f"GROUP BY product_id"
            ),
        ]

    @staticmethod
    def _is_recoverable_bootstrap_error(exc: Exception) -> bool:
        message = str(exc).lower()
        return "already exists" in message or "unknown catalog item" in message

    @staticmethod
    def _serialize_timestamp(value: Any) -> str | None:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        return None

    def _collect_status_sync(self) -> dict[str, Any]:
        objects = self._object_names()
        with self._connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT COUNT(*) AS hydrated_rows, MAX(occurred_at) AS max_occurred_at, MAX(ingested_at) AS max_ingested_at, MAX(kafka_offset) AS max_kafka_offset FROM {objects['entries_view']}"
                )
                entries_row = cursor.fetchone() or {}

                cursor.execute(f"SELECT COUNT(*) AS view_rows FROM {objects['sales_view']}")
                sales_row = cursor.fetchone() or {}

                cursor.execute(f"SELECT COUNT(*) AS view_rows FROM {objects['account_balances_view']}")
                accounts_row = cursor.fetchone() or {}

                cursor.execute(f"SELECT COUNT(*) AS view_rows FROM {objects['product_metrics_view']}")
                products_row = cursor.fetchone() or {}

                cursor.execute(
                    f"SELECT MAX(\"offset\") AS max_offset FROM (SELECT upper(partition)::uint8 AS partition, \"offset\" FROM {objects['progress']}) AS progress_rows WHERE partition IS NOT NULL"
                )
                progress_row = cursor.fetchone() or {}

                cursor.execute(f"SELECT COUNT(*) AS pending_retractions FROM {objects['typed_view']} WHERE is_current = 0")
                retractions_row = cursor.fetchone() or {}

        hydrated_rows = int(entries_row.get("hydrated_rows", 0) or 0)
        max_occurred_at = entries_row.get("max_occurred_at")
        max_ingested_at = entries_row.get("max_ingested_at")
        now = datetime.now(timezone.utc)
        view_lag_ms = None
        freshness_ms = None
        if isinstance(max_ingested_at, datetime):
            view_lag_ms = max(int((now - max_ingested_at.astimezone(timezone.utc)).total_seconds() * 1000), 0)
        if isinstance(max_occurred_at, datetime):
            freshness_ms = max(int((now - max_occurred_at.astimezone(timezone.utc)).total_seconds() * 1000), 0)
        state = "ready"
        if hydrated_rows < self.target_hydration_rows:
            state = "warming_up"
        if view_lag_ms is not None and view_lag_ms > self.expected_view_lag_ms:
            state = "warming_up"
        if freshness_ms is not None and freshness_ms > self.expected_freshness_ms:
            state = "warming_up"
        return {
            "enabled": True,
            "state": state,
            "schema": self.schema,
            "topic": self.kafka_topic,
            "group_id_prefix": self.group_id_prefix,
            "objects": objects,
            "hydrated_rows": hydrated_rows,
            "target_hydration_rows": self.target_hydration_rows,
            "view_count": {
                "sales": int(sales_row.get("view_rows", 0) or 0),
                "accounts": int(accounts_row.get("view_rows", 0) or 0),
                "products": int(products_row.get("view_rows", 0) or 0),
            },
            "pending_retractions": int(retractions_row.get("pending_retractions", 0) or 0),
            "last_visible_occurred_at": self._serialize_timestamp(max_occurred_at),
            "last_visible_ingested_at": self._serialize_timestamp(max_ingested_at),
            "last_source_offset": int(progress_row.get("max_offset", 0) or 0),
            "view_lag_ms": view_lag_ms,
            "expected_view_lag_ms": self.expected_view_lag_ms,
            "freshness_ms": freshness_ms,
            "expected_freshness_ms": self.expected_freshness_ms,
            "updated_at": now.isoformat(),
        }

    def _bootstrap_sync(self) -> dict[str, Any]:
        with self._connect() as connection:
            with connection.cursor() as cursor:
                for statement in self._bootstrap_statements():
                    try:
                        cursor.execute(statement)
                    except Exception as exc:
                        if self._is_recoverable_bootstrap_error(exc):
                            continue
                        raise
        return self._collect_status_sync()

    async def bootstrap_forever(self) -> None:
        if not self._runtime_enabled():
            self.status = {
                **self.status,
                "enabled": self.enabled,
                "state": "inactive",
                "reason": "materialize stack not active for this run",
            }
            return

        attempt = 0
        while self.max_attempts == 0 or attempt < self.max_attempts:
            attempt += 1
            self.status = {**self.status, "enabled": True, "state": "bootstrapping", "attempt": attempt}
            try:
                next_status = await asyncio.to_thread(self._bootstrap_sync)
                self.status = {**next_status, "attempt": attempt, "last_success_at": datetime.now(timezone.utc).isoformat()}
                return
            except Exception as exc:
                self.status = {
                    **self.status,
                    "enabled": True,
                    "state": "error",
                    "attempt": attempt,
                    "last_error": str(exc),
                }
                await asyncio.sleep(self.retry_seconds)

    async def current_status(self) -> dict[str, Any]:
        if not self._runtime_enabled():
            return {**self.status}
        if self.status.get("state") in {"ready", "warming_up"}:
            try:
                refreshed = await asyncio.to_thread(self._collect_status_sync)
                self.status = {
                    **self.status,
                    **refreshed,
                    "last_success_at": self.status.get("last_success_at") or datetime.now(timezone.utc).isoformat(),
                }
            except Exception as exc:
                self.status = {**self.status, "state": "degraded", "last_error": str(exc)}
        return {**self.status}