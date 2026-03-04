import os
import json
from datetime import datetime, timezone
from typing import Any

import httpx


class DashboardRepository:
    def __init__(self) -> None:
        self.base_url = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")
        self.db = os.getenv("CLICKHOUSE_DB", "ledger")
        self.user = os.getenv("CLICKHOUSE_USER", "ledger_app")
        self.password = os.getenv("CLICKHOUSE_PASSWORD", "ledger_app_pass")
        self.client = httpx.AsyncClient(timeout=2.5)

    async def _query(self, sql: str) -> str:
        response = await self.client.post(
            f"{self.base_url}/",
            params={"database": self.db, "query": sql},
            auth=(self.user, self.password),
        )
        response.raise_for_status()
        return response.text.strip()

    async def get_summary(self, as_of: str | None = None) -> dict[str, Any]:
        cutoff = as_of or datetime.now(timezone.utc).isoformat().replace("T", " ").replace("+00:00", "")
        sql = f"""
        SELECT
            round(sumIf(signed_amount, account_code = '1.1.01.01-Caixa'), 2) AS cash,
            round(sumIf(signed_amount, account_code = '1.1.03.01-Estoque'), 2) AS inventory,
            round(abs(sumIf(signed_amount, statement_section = 'liability')), 2) AS liabilities,
            round(abs(sumIf(signed_amount, statement_section = 'revenue')), 2) AS revenue,
            round(sumIf(signed_amount, statement_section = 'expense'), 2) AS expense,
            round(sumIf(signed_amount, account_code = '4.1.01.01-CMV'), 2) AS cmv
        FROM ledger.entries
        WHERE is_current = 1
          AND occurred_at <= parseDateTime64BestEffort('{cutoff}', 3)
        """.strip()

        raw = await self._query(sql)
        values = [float(part) if part else 0.0 for part in raw.split("\t")]
        while len(values) < 6:
            values.append(0.0)

        cash, inventory, liabilities, revenue, expense, cmv = values[:6]
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

    async def get_recent_entries(self, limit: int = 50, as_of: str | None = None) -> list[dict[str, Any]]:
        cutoff_clause = ""
        if as_of:
            normalized = as_of.replace("T", " ").replace("+00:00", "")
            cutoff_clause = f"AND occurred_at <= parseDateTime64BestEffort('{normalized}', 3)"

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
            source_payload_hash,
            occurred_at,
            ingested_at,
            revision
        FROM ledger.entries
        WHERE is_current = 1
        {cutoff_clause}
        ORDER BY occurred_at DESC
        LIMIT {int(limit)}
        FORMAT JSONEachRow
        """.strip()

        response = await self.client.post(
            f"{self.base_url}/",
            params={"database": self.db, "query": sql},
            auth=(self.user, self.password),
        )
        response.raise_for_status()

        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        entries: list[dict[str, Any]] = []
        for line in lines:
            entries.append(json.loads(line))
        return entries
