import os
import asyncio
from datetime import datetime, timezone
from typing import Any

import httpx


class DashboardRepository:
    def __init__(self) -> None:
        self.router_url = os.getenv("DRUID_ROUTER_URL", "http://druid-router:8888")
        self.datasource = os.getenv("DRUID_DATASOURCE", "ledger_events")
        self.master_data_url = os.getenv("MASTER_DATA_URL", "http://master-data:8091")
        self.client = httpx.AsyncClient(timeout=4.0)

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("'", "''")

    async def _query(self, sql: str) -> list[dict[str, Any]]:
        try:
            response = await self.client.post(
                f"{self.router_url}/druid/v2/sql",
                json={"query": sql},
                headers={"Content-Type": "application/json"},
            )
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, list) else []
        except Exception:
            return []

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

    def _build_where(
        self,
        filters: dict[str, str | None],
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> str:
        clauses = ["is_current = 1"]

        if start_at:
            normalized_start_at = start_at.replace("T", " ").replace("+00:00", "")
            clauses.append(f'"__time" >= TIME_PARSE(\'{self._escape(normalized_start_at)}\')')

        upper_bound = end_at or as_of
        if upper_bound:
            normalized_upper_bound = upper_bound.replace("T", " ").replace("+00:00", "")
            clauses.append(f'"__time" <= TIME_PARSE(\'{self._escape(normalized_upper_bound)}\')')

        for field, value in filters.items():
            if not value:
                continue
            normalized = self._escape(value.strip())
            if not normalized:
                continue
            clauses.append(f"{field} = '{normalized}'")

        return " AND ".join(clauses)

    async def get_summary(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        cutoff = end_at or as_of or datetime.now(timezone.utc).isoformat().replace("T", " ").replace("+00:00", "")
        where_clause = self._build_where(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at or cutoff)

        sql = f"""
        SELECT
            COALESCE(SUM(CASE WHEN account_role = 'cash' THEN signed_amount ELSE 0 END), 0) AS cash,
            COALESCE(SUM(CASE WHEN account_role = 'bank_accounts' THEN signed_amount ELSE 0 END), 0) AS bank_accounts,
            COALESCE(SUM(CASE WHEN account_role = 'recoverable_tax' THEN signed_amount ELSE 0 END), 0) AS recoverable_tax,
            COALESCE(SUM(CASE WHEN account_role = 'inventory' THEN signed_amount ELSE 0 END), 0) AS inventory,
            ABS(COALESCE(SUM(CASE WHEN account_role = 'accounts_payable' THEN signed_amount ELSE 0 END), 0)) AS accounts_payable,
            ABS(COALESCE(SUM(CASE WHEN account_role = 'tax_payable' THEN signed_amount ELSE 0 END), 0)) AS tax_payable,
            ABS(COALESCE(SUM(CASE WHEN account_role = 'revenue' THEN signed_amount ELSE 0 END), 0)) AS revenue,
            COALESCE(SUM(CASE WHEN account_role = 'returns' THEN signed_amount ELSE 0 END), 0) AS returns,
            COALESCE(SUM(CASE WHEN account_role = 'marketplace_fees' THEN signed_amount ELSE 0 END), 0) AS marketplace_fees,
            COALESCE(SUM(CASE WHEN account_role = 'outbound_freight' THEN signed_amount ELSE 0 END), 0) AS freight_out,
            COALESCE(SUM(CASE WHEN account_role = 'bank_fees' THEN signed_amount ELSE 0 END), 0) AS bank_fees,
            COALESCE(SUM(CASE WHEN account_role = 'cogs' THEN signed_amount ELSE 0 END), 0) AS cmv,
            COALESCE(SUM(CASE WHEN statement_section = 'expense' AND account_role NOT IN ('cogs', 'marketplace_fees', 'outbound_freight', 'bank_fees') THEN signed_amount ELSE 0 END), 0) AS other_expenses
        FROM \"{self.datasource}\"
        WHERE {where_clause}
        """.strip()

        rows = await self._query(sql)
        row = rows[0] if rows else {}

        cash = round(float(row.get("cash", 0.0)), 2)
        bank_accounts = round(float(row.get("bank_accounts", 0.0)), 2)
        recoverable_tax = round(float(row.get("recoverable_tax", 0.0)), 2)
        inventory = round(float(row.get("inventory", 0.0)), 2)
        accounts_payable = round(float(row.get("accounts_payable", 0.0)), 2)
        tax_payable = round(float(row.get("tax_payable", 0.0)), 2)
        revenue = round(float(row.get("revenue", 0.0)), 2)
        returns = round(float(row.get("returns", 0.0)), 2)
        marketplace_fees = round(float(row.get("marketplace_fees", 0.0)), 2)
        freight_out = round(float(row.get("freight_out", 0.0)), 2)
        bank_fees = round(float(row.get("bank_fees", 0.0)), 2)
        cmv = round(float(row.get("cmv", 0.0)), 2)
        other_expenses = round(float(row.get("other_expenses", 0.0)), 2)
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
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> list[dict[str, Any]]:
        where_clause = self._build_where(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at)

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
            TIME_FORMAT("__time", 'yyyy-MM-dd HH:mm:ss.SSS') AS occurred_at,
            ingested_at,
            revision
        FROM \"{self.datasource}\"
        WHERE {where_clause}
        ORDER BY "__time" DESC
        LIMIT {int(limit)}
        """.strip()

        rows = await self._query(sql)
        return rows if isinstance(rows, list) else []

    async def _distinct(self, field: str) -> list[str]:
        sql = f"""
        SELECT DISTINCT {field} AS value
        FROM \"{self.datasource}\"
        WHERE {field} IS NOT NULL AND {field} != ''
        ORDER BY value
        LIMIT 2000
        """.strip()
        rows = await self._query(sql)
        return [str(item.get("value")) for item in rows if item.get("value") is not None]

    async def get_filter_options(self) -> dict[str, list[str]]:
        return {
            "product_names": await self._distinct("product_name"),
            "product_categories": await self._distinct("product_category"),
            "supplier_names": await self._distinct("supplier_name"),
            "event_types": await self._distinct("ontology_event_type"),
            "entry_categories": await self._distinct("entry_category"),
            "account_codes": await self._distinct("account_code"),
            "warehouse_ids": await self._distinct("warehouse_id"),
            "channels": await self._distinct("channel_name"),
            "entry_sides": await self._distinct("entry_side"),
            "ontology_sources": await self._distinct("ontology_source"),
        }

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
            self._query(
                f"""
                SELECT
                    account_code,
                    MAX(account_name) AS account_name,
                    MAX(account_role) AS account_role,
                    MAX(statement_section) AS statement_section,
                    ROUND(SUM(signed_amount), 2) AS current_balance,
                    COUNT(*) AS entry_count
                FROM \"{self.datasource}\"
                WHERE is_current = 1
                GROUP BY account_code
                ORDER BY account_code
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
            self._query(
                f"""
                SELECT
                    product_id,
                    MAX(product_name) AS product_name,
                    ROUND(SUM(CASE WHEN account_role = 'inventory' THEN CASE WHEN entry_side = 'debit' THEN quantity ELSE -quantity END ELSE 0 END), 3) AS stock_quantity,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN quantity ELSE 0 END), 3) AS sold_quantity,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'return' AND account_role = 'inventory' THEN quantity ELSE 0 END), 3) AS returned_quantity,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'purchase' AND account_role = 'inventory' THEN unit_price ELSE 0 END), 2) AS purchase_price_sum,
                    SUM(CASE WHEN ontology_event_type = 'purchase' AND account_role = 'inventory' THEN 1 ELSE 0 END) AS purchase_event_count,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN unit_price ELSE 0 END), 2) AS sale_price_sum,
                    SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN 1 ELSE 0 END) AS sale_event_count
                FROM \"{self.datasource}\"
                WHERE is_current = 1 AND product_id IS NOT NULL AND product_id != ''
                GROUP BY product_id
                ORDER BY product_id
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

    async def get_workspace_snapshot(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        summary, entries, master_data, accounts, products = await asyncio.gather(
            self.get_summary(as_of=as_of, start_at=start_at, end_at=end_at, filters=filters),
            self.get_recent_entries(limit=30, as_of=as_of, start_at=start_at, end_at=end_at, filters=filters),
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
