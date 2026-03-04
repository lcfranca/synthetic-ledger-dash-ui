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
            entry_side String,
            account_code String,
            account_name String,
            statement_section String,
            amount Float64,
            signed_amount Float64,
            currency String,
            ontology_event_type String,
            ontology_description String,
            ontology_source String,
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
