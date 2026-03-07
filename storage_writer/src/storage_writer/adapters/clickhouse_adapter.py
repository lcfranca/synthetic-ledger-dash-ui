import os

import httpx
import orjson

from .base import StorageAdapter


class ClickHouseAdapter(StorageAdapter):
    name = "clickhouse"

    def __init__(self) -> None:
        self.base_url = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")
        self.db = os.getenv("CLICKHOUSE_DB", "ledger")
        self.user = os.getenv("CLICKHOUSE_USER", "default")
        self.password = os.getenv("CLICKHOUSE_PASSWORD", "")
        self.client = httpx.AsyncClient(timeout=2.0)
        self._schema_ready = False

    async def _ensure_schema(self) -> None:
        if self._schema_ready:
            return

        create_db = "CREATE DATABASE IF NOT EXISTS ledger"
        create_table = """
        CREATE TABLE IF NOT EXISTS ledger.entries (
            entry_id String,
            event_id String,
            trace_id String,
            company_id String,
            tenant_id String,
            company_name String,
            entry_side String,
            account_code String,
            account_name String,
            account_role String,
            statement_section String,
            amount Float64,
            signed_amount Float64,
            quantity Float64,
            unit_price Float64,
            gross_amount Float64,
            net_amount Float64,
            tax_amount Float64,
            marketplace_fee_amount Float64,
            inventory_cost_total Float64,
            currency String,
            ontology_event_type String,
            ontology_description String,
            ontology_source String,
            product_id String,
            product_name String,
            product_category String,
            product_brand String,
            supplier_id Nullable(String),
            supplier_name Nullable(String),
            customer_id Nullable(String),
            warehouse_id String,
            warehouse_name String,
            channel String,
            channel_name String,
            entry_category String,
            order_id String,
            source_payload_hash String,
            schema_version String,
            occurred_at DateTime64(3, 'UTC'),
            ingested_at DateTime64(3, 'UTC'),
            valid_from DateTime64(3, 'UTC'),
            valid_to Nullable(DateTime64(3, 'UTC')),
            is_current UInt8,
            revision UInt32,
            created_at DateTime64(3, 'UTC')
        )
        ENGINE = MergeTree
        ORDER BY (company_id, occurred_at, entry_id)
        """.strip()

        db_response = await self.client.post(
            f"{self.base_url}/",
            params={"query": create_db},
            auth=(self.user, self.password),
        )
        db_response.raise_for_status()

        table_response = await self.client.post(
            f"{self.base_url}/",
            params={"query": create_table},
            auth=(self.user, self.password),
        )
        table_response.raise_for_status()

        alter_statements = [
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS company_name String DEFAULT ''",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS account_role String DEFAULT 'other'",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS quantity Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS unit_price Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS gross_amount Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS net_amount Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS tax_amount Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS marketplace_fee_amount Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS inventory_cost_total Float64 DEFAULT 0",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS product_id String",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS product_name String DEFAULT ''",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS product_category String DEFAULT ''",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS product_brand String DEFAULT ''",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS supplier_id Nullable(String)",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS supplier_name Nullable(String)",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS customer_id Nullable(String)",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS warehouse_id String DEFAULT 'unknown-warehouse'",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS warehouse_name String DEFAULT 'unknown-warehouse'",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS channel String DEFAULT 'unknown-channel'",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS channel_name String DEFAULT 'unknown-channel'",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS entry_category String DEFAULT 'operacional'",
            "ALTER TABLE ledger.entries ADD COLUMN IF NOT EXISTS order_id String DEFAULT ''",
        ]
        for statement in alter_statements:
            alter_response = await self.client.post(
                f"{self.base_url}/",
                params={"query": statement},
                auth=(self.user, self.password),
            )
            alter_response.raise_for_status()
        self._schema_ready = True

    async def healthy(self) -> bool:
        try:
            response = await self.client.get(f"{self.base_url}/ping")
            return response.status_code == 200
        except Exception:
            return False

    async def write_event(self, event: dict) -> None:
        await self._ensure_schema()
        query = """
            INSERT INTO ledger.entries FORMAT JSONEachRow
        """.strip()
        for field in ("occurred_at", "ingested_at", "valid_from", "created_at"):
            value = event.get(field)
            if isinstance(value, str):
                normalized = value.replace("T", " ")
                if normalized.endswith("Z"):
                    normalized = normalized[:-1]
                if normalized.endswith("+00:00"):
                    normalized = normalized[:-6]
                event[field] = normalized
        response = await self.client.post(
            f"{self.base_url}/?database={self.db}&query={query}",
            content=orjson.dumps(event) + b"\n",
            auth=(self.user, self.password),
        )
        if response.status_code >= 400:
            raise RuntimeError(f"ClickHouse insert failed: {response.text[:400]}")
