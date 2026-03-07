import os
import json
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx


class DashboardRepository:
    def __init__(self) -> None:
        self.base_url = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")
        self.db = os.getenv("CLICKHOUSE_DB", "ledger")
        self.user = os.getenv("CLICKHOUSE_USER", "ledger_app")
        self.password = os.getenv("CLICKHOUSE_PASSWORD", "ledger_app_pass")
        self.master_data_url = os.getenv("MASTER_DATA_URL", "http://master-data:8091")
        self.client = httpx.AsyncClient(timeout=2.5)

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("'", "''")

    def _build_filters(self, filters: dict[str, str | None], as_of: str | None = None) -> str:
        clauses = ["is_current = 1"]

        if as_of:
            normalized_as_of = as_of.replace("T", " ").replace("+00:00", "")
            clauses.append(f"occurred_at <= parseDateTime64BestEffort('{self._escape(normalized_as_of)}', 3)")

        for field, value in filters.items():
            if not value:
                continue
            normalized_value = self._escape(value.strip())
            if not normalized_value:
                continue
            clauses.append(f"{field} = '{normalized_value}'")

        return " AND ".join(clauses)

    async def _query(self, sql: str) -> str:
        response = await self.client.post(
            f"{self.base_url}/",
            params={"database": self.db, "query": sql},
            auth=(self.user, self.password),
        )
        response.raise_for_status()
        return response.text.strip()

    async def _query_json_rows(self, sql: str) -> list[dict[str, Any]]:
        response = await self.client.post(
            f"{self.base_url}/",
            params={"database": self.db, "query": sql},
            auth=(self.user, self.password),
        )
        response.raise_for_status()
        lines = [line.strip() for line in response.text.splitlines() if line.strip()]
        return [json.loads(line) for line in lines]

    async def _fetch_json(self, path: str, default: Any) -> Any:
        try:
            response = await self.client.get(f"{self.master_data_url}{path}")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, type(default)) else default
        except Exception:
            return default

    @staticmethod
    def _supply_plan(product: dict[str, Any], current_stock_quantity: float, sold_quantity: float) -> dict[str, Any]:
        effective_stock = max(round(current_stock_quantity, 3), 0.0)
        demand_weight = max(float(product.get("demand_weight", 0.0) or 0.0), 0.1)
        daily_demand_units = round(max(sold_quantity / 30.0, demand_weight), 3)
        coverage_days = round(effective_stock / daily_demand_units, 1) if daily_demand_units > 0 else None
        reorder_point = float(product.get("reorder_point", 0.0) or 0.0)
        target_stock = float(product.get("target_stock", 0.0) or 0.0)
        suggested_purchase_quantity = round(max(target_stock - effective_stock, 0.0), 3)
        suggested_supplier_name = str(product.get("supplier_name") or product.get("preferred_supplier_id") or "Fornecedor padrão")
        needs_restock = effective_stock <= reorder_point
        if needs_restock and suggested_purchase_quantity > 0:
            purchase_recommendation = f"Comprar {suggested_purchase_quantity:g} un de {suggested_supplier_name}"
        else:
            purchase_recommendation = f"Sem compra sugerida para {suggested_supplier_name}"
        return {
            "daily_demand_units": daily_demand_units,
            "coverage_days": coverage_days,
            "suggested_purchase_quantity": suggested_purchase_quantity,
            "suggested_purchase_supplier_name": suggested_supplier_name,
            "purchase_recommendation": purchase_recommendation,
            "needs_restock": needs_restock,
        }

    async def get_summary(self, *, as_of: str | None = None, filters: dict[str, str | None] | None = None) -> dict[str, Any]:
        cutoff = as_of or datetime.now(timezone.utc).isoformat().replace("T", " ").replace("+00:00", "")
        where_clause = self._build_filters(filters or {}, cutoff)
        sql = f"""
        SELECT
            round(sumIf(signed_amount, account_role = 'cash'), 2) AS cash,
            round(sumIf(signed_amount, account_role = 'bank_accounts'), 2) AS bank_accounts,
            round(sumIf(signed_amount, account_role = 'recoverable_tax'), 2) AS recoverable_tax,
            round(sumIf(signed_amount, account_role = 'inventory'), 2) AS inventory,
            round(abs(sumIf(signed_amount, account_role = 'accounts_payable')), 2) AS accounts_payable,
            round(abs(sumIf(signed_amount, account_role = 'tax_payable')), 2) AS tax_payable,
            round(abs(sumIf(signed_amount, account_role = 'revenue')), 2) AS revenue,
            round(sumIf(signed_amount, account_role = 'returns'), 2) AS returns,
            round(sumIf(signed_amount, account_role = 'marketplace_fees'), 2) AS marketplace_fees,
            round(sumIf(signed_amount, account_role = 'outbound_freight'), 2) AS freight_out,
            round(sumIf(signed_amount, account_role = 'bank_fees'), 2) AS bank_fees,
            round(sumIf(signed_amount, account_role = 'cogs'), 2) AS cmv,
            round(sumIf(signed_amount, statement_section = 'expense' AND account_role NOT IN ('cogs', 'marketplace_fees', 'outbound_freight', 'bank_fees')), 2) AS other_expenses
        FROM ledger.entries
        WHERE {where_clause}
        """.strip()

        raw = await self._query(sql)
        values = [float(part) if part else 0.0 for part in raw.split("\t")]
        while len(values) < 13:
            values.append(0.0)

        (
            cash,
            bank_accounts,
            recoverable_tax,
            inventory,
            accounts_payable,
            tax_payable,
            revenue,
            returns,
            marketplace_fees,
            freight_out,
            bank_fees,
            cmv,
            other_expenses,
        ) = values[:13]
        liabilities_total = round(accounts_payable + tax_payable, 2)
        net_revenue = round(revenue - returns, 2)
        operating_expenses = round(marketplace_fees + freight_out + bank_fees + other_expenses, 2)
        expenses_total = round(operating_expenses + cmv, 2)
        net_income = round(net_revenue - expenses_total, 2)
        assets_total = round(cash + bank_accounts + recoverable_tax + inventory, 2)
        liabilities_and_equity = round(liabilities_total + net_income, 2)
        difference = round(assets_total - liabilities_and_equity, 2)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of": cutoff,
            "balance_sheet": {
                "assets": {
                    "cash": cash,
                    "bank_accounts": bank_accounts,
                    "recoverable_tax": recoverable_tax,
                    "inventory": inventory,
                    "total": assets_total,
                },
                "liabilities": {
                    "accounts_payable": accounts_payable,
                    "tax_payable": tax_payable,
                    "total": liabilities_total,
                },
                "equity": {"current_earnings": net_income},
                "total_liabilities_and_equity": liabilities_and_equity,
                "difference": difference,
            },
            "income_statement": {
                "revenue": revenue,
                "returns": returns,
                "net_revenue": net_revenue,
                "marketplace_fees": marketplace_fees,
                "freight_out": freight_out,
                "bank_fees": bank_fees,
                "other_expenses": other_expenses,
                "operating_expenses": operating_expenses,
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
        where_clause = self._build_filters(filters or {}, as_of)

        sql = f"""
        SELECT
            entry_id,
            event_id,
            trace_id,
            entry_side,
            account_code,
            account_name,
            account_role,
            amount,
            signed_amount,
            quantity,
            unit_price,
            currency,
            ontology_event_type,
            ontology_description,
            ontology_source,
            product_id,
            product_name,
            product_category,
            product_brand,
            supplier_id,
            supplier_name,
            customer_id,
            warehouse_id,
            warehouse_name,
            channel,
            channel_name,
            entry_category,
            order_id,
            source_payload_hash,
            occurred_at,
            ingested_at,
            revision
        FROM ledger.entries
        WHERE {where_clause}
        ORDER BY occurred_at DESC
        LIMIT {int(limit)}
        FORMAT JSONEachRow
        """.strip()

        return await self._query_json_rows(sql)

    async def get_filter_options(self) -> dict[str, list[str]]:
        sql = """
        SELECT
            groupUniqArrayIf(product_name, product_name != '') AS product_names,
            groupUniqArrayIf(product_category, product_category != '') AS product_categories,
            groupUniqArrayIf(supplier_name, supplier_name IS NOT NULL AND supplier_name != '') AS supplier_names,
            groupUniqArrayIf(ontology_event_type, ontology_event_type != '') AS event_types,
            groupUniqArrayIf(entry_category, entry_category != '') AS entry_categories,
            groupUniqArrayIf(account_code, account_code != '') AS account_codes,
            groupUniqArrayIf(warehouse_id, warehouse_id != '') AS warehouse_ids,
            groupUniqArrayIf(channel_name, channel_name != '') AS channels,
            groupUniqArrayIf(entry_side, entry_side != '') AS entry_sides,
            groupUniqArrayIf(ontology_source, ontology_source != '') AS ontology_sources
        FROM ledger.entries
        WHERE is_current = 1
        FORMAT JSONEachRow
        """.strip()

        response = await self.client.post(
            f"{self.base_url}/",
            params={"database": self.db, "query": sql},
            auth=(self.user, self.password),
        )
        response.raise_for_status()

        line = next((item for item in response.text.splitlines() if item.strip()), "{}")
        payload = json.loads(line)
        return {key: sorted(set(value or [])) for key, value in payload.items()}

    async def get_master_data_overview(self) -> dict[str, Any]:
        health, company, products, accounts, channels = await asyncio.gather(
            self._fetch_json("/health", {}),
            self._fetch_json("/api/v1/master-data/company", {}),
            self._fetch_json("/api/v1/master-data/products", []),
            self._fetch_json("/api/v1/master-data/accounts", []),
            self._fetch_json("/api/v1/master-data/channels", []),
        )
        channel_map = {item.get("channel_id"): item.get("channel_name") for item in channels if isinstance(item, dict)}
        account_sections: dict[str, int] = {}
        opening_inventory_units = 0
        opening_inventory_positions = 0
        for account in accounts:
            section = str(account.get("statement_section", "other"))
            account_sections[section] = account_sections.get(section, 0) + 1
        for product in products:
            stock_map = product.get("initial_stock") or {}
            if isinstance(stock_map, dict):
                opening_inventory_positions += len(stock_map)
                opening_inventory_units += sum(int(value) for value in stock_map.values())
            product["channel_names"] = [channel_map.get(channel_id, channel_id) for channel_id in product.get("channel_ids", [])]
        counts = health.get("counts") if isinstance(health, dict) else {}
        return {
            "company": company,
            "products": products,
            "accounts": accounts,
            "channels": channels,
            "stats": {
                "product_count": len(products),
                "channel_count": len(channels),
                "account_count": len(accounts),
                "supplier_count": int(counts.get("suppliers", 0)),
                "warehouse_count": int(counts.get("warehouses", 0)),
                "opening_inventory_units": opening_inventory_units,
                "opening_inventory_positions": opening_inventory_positions,
                "account_sections": account_sections,
            },
        }

    async def get_account_catalog(self) -> list[dict[str, Any]]:
        accounts, balances = await asyncio.gather(
            self._fetch_json("/api/v1/master-data/accounts", []),
            self._query_json_rows(
                """
                SELECT
                    account_code,
                    any(account_name) AS account_name,
                    any(account_role) AS account_role,
                    any(statement_section) AS statement_section,
                    round(sum(signed_amount), 2) AS current_balance,
                    count() AS entry_count
                FROM ledger.entries
                WHERE is_current = 1
                GROUP BY account_code
                ORDER BY account_code
                FORMAT JSONEachRow
                """.strip()
            ),
        )
        balances_by_code = {item["account_code"]: item for item in balances}
        rows = []
        for account in accounts:
            balance = balances_by_code.get(account["account_code"], {})
            rows.append(
                {
                    **account,
                    "current_balance": round(float(balance.get("current_balance", 0.0)), 2),
                    "entry_count": int(balance.get("entry_count", 0)),
                }
            )
        return rows

    async def get_product_catalog(self) -> list[dict[str, Any]]:
        products, channels, aggregates = await asyncio.gather(
            self._fetch_json("/api/v1/master-data/products", []),
            self._fetch_json("/api/v1/master-data/channels", []),
            self._query_json_rows(
                """
                SELECT
                    product_id,
                    any(product_name) AS product_name,
                    round(sumIf(if(entry_side = 'debit', quantity, -quantity), account_role = 'inventory'), 3) AS stock_quantity,
                    round(sumIf(quantity, ontology_event_type = 'sale' AND account_role = 'inventory'), 3) AS sold_quantity,
                    round(sumIf(quantity, ontology_event_type = 'return' AND account_role = 'inventory'), 3) AS returned_quantity,
                    round(sumIf(unit_price, ontology_event_type = 'purchase' AND account_role = 'inventory'), 2) AS purchase_price_sum,
                    countIf(ontology_event_type = 'purchase' AND account_role = 'inventory') AS purchase_event_count,
                    round(sumIf(unit_price, ontology_event_type = 'sale' AND account_role = 'inventory'), 2) AS sale_price_sum,
                    countIf(ontology_event_type = 'sale' AND account_role = 'inventory') AS sale_event_count
                FROM ledger.entries
                WHERE is_current = 1 AND product_id != ''
                GROUP BY product_id
                ORDER BY product_id
                FORMAT JSONEachRow
                """.strip()
            ),
        )
        channel_map = {item.get("channel_id"): item.get("channel_name") for item in channels if isinstance(item, dict)}
        aggregates_by_product = {item["product_id"]: item for item in aggregates}
        rows = []
        for product in products:
            aggregate = aggregates_by_product.get(product["product_id"], {})
            purchase_event_count = int(aggregate.get("purchase_event_count", 0) or 0)
            sale_event_count = int(aggregate.get("sale_event_count", 0) or 0)
            average_purchase_price = round(float(aggregate.get("purchase_price_sum", 0.0)) / purchase_event_count, 2) if purchase_event_count else round(float(product.get("base_cost", 0.0)), 2)
            average_sale_price = round(float(aggregate.get("sale_price_sum", 0.0)) / sale_event_count, 2) if sale_event_count else round(float(product.get("base_price", 0.0)), 2)
            opening_stock_quantity = round(sum(float(value) for value in (product.get("initial_stock") or {}).values()), 3)
            stock_quantity = round(opening_stock_quantity + float(aggregate.get("stock_quantity", 0.0)), 3)
            sold_quantity = round(max(float(aggregate.get("sold_quantity", 0.0)) - float(aggregate.get("returned_quantity", 0.0)), 0.0), 3)
            supply_plan = self._supply_plan(product, stock_quantity, sold_quantity)
            rows.append(
                {
                    **product,
                    "registered_channels": [channel_map.get(channel_id, channel_id) for channel_id in product.get("channel_ids", [])],
                    "opening_stock_quantity": opening_stock_quantity,
                    "current_stock_quantity": stock_quantity,
                    "sold_quantity": sold_quantity,
                    "returned_quantity": round(float(aggregate.get("returned_quantity", 0.0)), 3),
                    "average_purchase_price": average_purchase_price,
                    "average_sale_price": average_sale_price,
                    **supply_plan,
                }
            )
        return rows

    async def get_workspace_snapshot(self) -> dict[str, Any]:
        summary, entries, master_data, accounts, products = await asyncio.gather(
            self.get_summary(),
            self.get_recent_entries(limit=30),
            self.get_master_data_overview(),
            self.get_account_catalog(),
            self.get_product_catalog(),
        )
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "entries": entries,
            "master_data": master_data,
            "account_catalog": accounts,
            "product_catalog": products,
        }
