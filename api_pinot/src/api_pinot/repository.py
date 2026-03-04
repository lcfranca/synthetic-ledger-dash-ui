import os
from datetime import datetime, timezone
from typing import Any

import httpx


class DashboardRepository:
    def __init__(self) -> None:
        self.broker_url = os.getenv("PINOT_BROKER_URL", "http://pinot-broker:8099")
        self.table = os.getenv("PINOT_TABLE", "ledger_events")
        self.client = httpx.AsyncClient(timeout=4.0)

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _to_epoch_millis(value: str) -> int:
        normalized = value.replace("Z", "+00:00")
        try:
            return int(datetime.fromisoformat(normalized).timestamp() * 1000)
        except ValueError:
            return int(datetime.now(timezone.utc).timestamp() * 1000)

    async def _query_rows(self, sql: str) -> list[dict[str, Any]]:
        try:
            response = await self.client.post(
                f"{self.broker_url}/query/sql",
                json={"sql": sql},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            result_table = payload.get("resultTable") or {}
            data_schema = result_table.get("dataSchema") or {}
            columns = data_schema.get("columnNames") or []
            rows = result_table.get("rows") or []
            if not columns or not isinstance(rows, list):
                return []
            return [dict(zip(columns, row)) for row in rows]
        except Exception:
            return []

    def _build_where(self, filters: dict[str, str | None], as_of: str | None = None) -> str:
        clauses = ["is_current = 1"]

        if as_of:
            clauses.append(f"occurred_at_epoch_ms <= {self._to_epoch_millis(as_of)}")

        for field, value in filters.items():
            if not value:
                continue
            normalized = self._escape(value.strip())
            if not normalized:
                continue
            clauses.append(f"{field} = '{normalized}'")

        return " AND ".join(clauses)

    async def get_summary(self, *, as_of: str | None = None, filters: dict[str, str | None] | None = None) -> dict[str, Any]:
        cutoff = as_of or datetime.now(timezone.utc).isoformat().replace("T", " ").replace("+00:00", "")
        where_clause = self._build_where(filters or {}, cutoff)

        sql = f"""
        SELECT
            COALESCE(SUM(CASE WHEN account_code = '1.1.01.01-Caixa' THEN signed_amount ELSE 0 END), 0) AS cash,
            COALESCE(SUM(CASE WHEN account_code = '1.1.03.01-Estoque' THEN signed_amount ELSE 0 END), 0) AS inventory,
            ABS(COALESCE(SUM(CASE WHEN statement_section = 'liability' THEN signed_amount ELSE 0 END), 0)) AS liabilities,
            ABS(COALESCE(SUM(CASE WHEN statement_section = 'revenue' THEN signed_amount ELSE 0 END), 0)) AS revenue,
            COALESCE(SUM(CASE WHEN statement_section = 'expense' THEN signed_amount ELSE 0 END), 0) AS expense,
            COALESCE(SUM(CASE WHEN account_code = '4.1.01.01-CMV' THEN signed_amount ELSE 0 END), 0) AS cmv
        FROM {self.table}
        WHERE {where_clause}
        """.strip()

        rows = await self._query_rows(sql)
        row = rows[0] if rows else {}

        cash = round(float(row.get("cash", 0.0)), 2)
        inventory = round(float(row.get("inventory", 0.0)), 2)
        liabilities = round(float(row.get("liabilities", 0.0)), 2)
        revenue = round(float(row.get("revenue", 0.0)), 2)
        expense = round(float(row.get("expense", 0.0)), 2)
        cmv = round(float(row.get("cmv", 0.0)), 2)
        expenses_total = round(expense + cmv, 2)
        net_income = round(revenue - expenses_total, 2)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of": cutoff,
            "balance_sheet": {
                "assets": {
                    "cash": cash,
                    "inventory": inventory,
                },
                "liabilities": {
                    "accounts_payable": liabilities,
                },
            },
            "income_statement": {
                "revenue": revenue,
                "expenses": expenses_total,
                "net_income": net_income,
                "cmv": cmv,
            },
        }

    async def get_recent_entries(
        self,
        *,
        limit: int = 50,
        as_of: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> list[dict[str, Any]]:
        where_clause = self._build_where(filters or {}, as_of)

        sql = f"""
        SELECT
            entry_id,
            event_id,
            trace_id,
            entry_side,
            account_code,
            account_name,
            amount,
            signed_amount,
            currency,
            ontology_event_type,
            ontology_description,
            ontology_source,
            product_id,
            supplier_id,
            customer_id,
            warehouse_id,
            channel,
            entry_category,
            source_payload_hash,
            occurred_at,
            ingested_at,
            revision
        FROM {self.table}
        WHERE {where_clause}
        ORDER BY occurred_at_epoch_ms DESC
        LIMIT {int(limit)}
        """.strip()

        rows = await self._query_rows(sql)
        return rows if isinstance(rows, list) else []

    async def _distinct(self, field: str) -> list[str]:
        sql = f"""
        SELECT DISTINCT {field} AS value
        FROM {self.table}
        WHERE {field} IS NOT NULL AND {field} != ''
        ORDER BY value
        LIMIT 2000
        """.strip()
        rows = await self._query_rows(sql)
        return [str(item.get("value")) for item in rows if item.get("value") is not None]

    async def get_filter_options(self) -> dict[str, list[str]]:
        return {
            "product_ids": await self._distinct("product_id"),
            "supplier_ids": await self._distinct("supplier_id"),
            "event_types": await self._distinct("ontology_event_type"),
            "entry_categories": await self._distinct("entry_category"),
            "account_codes": await self._distinct("account_code"),
            "warehouse_ids": await self._distinct("warehouse_id"),
            "channels": await self._distinct("channel"),
            "entry_sides": await self._distinct("entry_side"),
            "ontology_sources": await self._distinct("ontology_source"),
        }
