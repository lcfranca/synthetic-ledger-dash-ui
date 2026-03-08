import asyncio
import os
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

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value in (None, "", "null"):
            return None
        return str(value)

    @staticmethod
    def _normalize_time(value: str) -> str:
        return value.replace("T", " ").replace("Z", "").replace("+00:00", "")

    async def _query_rows(self, sql: str) -> list[dict[str, Any]]:
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
        daily_demand_units = round(max(sold_quantity / 540.0, demand_weight * 0.55), 3)
        reorder_trigger = max(float(product.get("reorder_point", 0.0) or 0.0), daily_demand_units * 6.0)
        target_stock_level = max(float(product.get("target_stock", 0.0) or 0.0), daily_demand_units * 14.0)
        coverage_days = round(effective_stock / daily_demand_units, 1) if daily_demand_units > 0 else None
        suggested_purchase_quantity = round(max(target_stock_level - effective_stock, 0.0), 3) if effective_stock <= reorder_trigger else 0.0
        suggested_supplier_name = str(product.get("supplier_name") or product.get("preferred_supplier_id") or "Fornecedor padrão")
        needs_restock = effective_stock <= reorder_trigger
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

    @staticmethod
    def _percentage(numerator: float, denominator: float, digits: int = 2) -> float | None:
        if abs(denominator) < 0.005:
            return None
        return round((numerator / denominator) * 100.0, digits)

    @staticmethod
    def _normalize_breakdown_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: dict[str, dict[str, Any]] = {}
        for row in rows:
            raw_label = str(row.get("label") or "").strip()
            label = raw_label if raw_label and raw_label.lower() != "null" else "nao_informado"
            bucket = normalized.setdefault(
                label,
                {
                    "label": label,
                    "order_count": 0,
                    "quantity": 0.0,
                    "gross_sales": 0.0,
                    "net_sales": 0.0,
                },
            )
            bucket["order_count"] += int(row.get("order_count", 0) or 0)
            bucket["quantity"] = round(float(bucket["quantity"]) + float(row.get("quantity", 0.0) or 0.0), 3)
            bucket["gross_sales"] = round(float(bucket["gross_sales"]) + float(row.get("gross_sales", 0.0) or 0.0), 2)
            bucket["net_sales"] = round(float(bucket["net_sales"]) + float(row.get("net_sales", 0.0) or 0.0), 2)

        return sorted(normalized.values(), key=lambda item: float(item.get("net_sales", 0.0)), reverse=True)

    def _income_statement_metrics(
        self,
        *,
        revenue: float,
        returns: float,
        marketplace_fees: float,
        freight_out: float,
        bank_fees: float,
        financial_expenses: float,
        other_expenses: float,
        cmv: float,
    ) -> dict[str, float | None]:
        net_revenue = round(revenue - returns, 2)
        gross_profit = round(net_revenue - cmv, 2)
        operating_expenses = round(marketplace_fees + freight_out + bank_fees + other_expenses, 2)
        expenses_total = round(operating_expenses + financial_expenses + cmv, 2)
        net_income = round(net_revenue - expenses_total, 2)
        return {
            "net_revenue": net_revenue,
            "gross_profit": gross_profit,
            "operating_expenses": operating_expenses,
            "expenses": expenses_total,
            "net_income": net_income,
            "return_rate_pct": self._percentage(returns, revenue),
            "gross_margin_pct": self._percentage(gross_profit, net_revenue),
            "net_margin_pct": self._percentage(net_income, net_revenue),
            "expense_ratio_pct": self._percentage(operating_expenses, net_revenue),
        }

    def _inventory_snapshot_totals(self, product_catalog: list[dict[str, Any]]) -> dict[str, float]:
        inventory_value = 0.0
        inventory_units = 0.0
        for product in product_catalog:
            current_stock_quantity = max(float(product.get("current_stock_quantity", 0.0) or 0.0), 0.0)
            average_purchase_price = max(float(product.get("average_purchase_price", 0.0) or 0.0), 0.0)
            inventory_units += current_stock_quantity
            inventory_value += current_stock_quantity * average_purchase_price
        return {
            "inventory_value": round(inventory_value, 2),
            "inventory_units": round(inventory_units, 3),
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
            normalized_start = self._escape(self._normalize_time(start_at))
            clauses.append(f'"__time" >= TIME_PARSE(\'{normalized_start}\')')

        upper_bound = end_at or as_of
        if upper_bound:
            normalized_upper = self._escape(self._normalize_time(upper_bound))
            clauses.append(f'"__time" <= TIME_PARSE(\'{normalized_upper}\')')

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
            ABS(COALESCE(SUM(CASE WHEN account_role = 'short_term_loans' THEN signed_amount ELSE 0 END), 0)) AS short_term_loans,
            ABS(COALESCE(SUM(CASE WHEN account_role = 'tax_payable' THEN signed_amount ELSE 0 END), 0)) AS tax_payable,
            ABS(COALESCE(SUM(CASE WHEN account_role = 'revenue' THEN signed_amount ELSE 0 END), 0)) AS revenue,
            COALESCE(SUM(CASE WHEN account_role = 'returns' THEN signed_amount ELSE 0 END), 0) AS returns_amount,
            COALESCE(SUM(CASE WHEN account_role = 'marketplace_fees' THEN signed_amount ELSE 0 END), 0) AS marketplace_fees,
            COALESCE(SUM(CASE WHEN account_role = 'outbound_freight' THEN signed_amount ELSE 0 END), 0) AS freight_out,
            COALESCE(SUM(CASE WHEN account_role = 'bank_fees' THEN signed_amount ELSE 0 END), 0) AS bank_fees,
            COALESCE(SUM(CASE WHEN account_role = 'interest_expense' THEN signed_amount ELSE 0 END), 0) AS financial_expenses,
            COALESCE(SUM(CASE WHEN account_role = 'cogs' THEN signed_amount ELSE 0 END), 0) AS cmv,
            COALESCE(SUM(CASE WHEN statement_section = 'expense'
                AND account_role != 'cogs'
                AND account_role != 'marketplace_fees'
                AND account_role != 'outbound_freight'
                AND account_role != 'bank_fees'
                AND account_role != 'interest_expense'
            THEN signed_amount ELSE 0 END), 0) AS other_expenses
        FROM "{self.datasource}"
        WHERE {where_clause}
        """.strip()

        rows = await self._query_rows(sql)
        row = rows[0] if rows else {}

        cash = round(float(row.get("cash", 0.0)), 2)
        bank_accounts = round(float(row.get("bank_accounts", 0.0)), 2)
        recoverable_tax = round(float(row.get("recoverable_tax", 0.0)), 2)
        inventory = round(float(row.get("inventory", 0.0)), 2)
        accounts_payable = round(float(row.get("accounts_payable", 0.0)), 2)
        short_term_loans = round(float(row.get("short_term_loans", 0.0)), 2)
        tax_payable = round(float(row.get("tax_payable", 0.0)), 2)
        revenue = round(float(row.get("revenue", 0.0)), 2)
        returns = round(float(row.get("returns_amount", 0.0)), 2)
        marketplace_fees = round(float(row.get("marketplace_fees", 0.0)), 2)
        freight_out = round(float(row.get("freight_out", 0.0)), 2)
        bank_fees = round(float(row.get("bank_fees", 0.0)), 2)
        financial_expenses = round(float(row.get("financial_expenses", 0.0)), 2)
        cmv = round(float(row.get("cmv", 0.0)), 2)
        other_expenses = round(float(row.get("other_expenses", 0.0)), 2)
        metrics = self._income_statement_metrics(
            revenue=revenue,
            returns=returns,
            marketplace_fees=marketplace_fees,
            freight_out=freight_out,
            bank_fees=bank_fees,
            financial_expenses=financial_expenses,
            other_expenses=other_expenses,
            cmv=cmv,
        )
        liabilities_total = round(accounts_payable + short_term_loans + tax_payable, 2)
        net_revenue = round(float(metrics["net_revenue"] or 0.0), 2)
        gross_profit = round(float(metrics["gross_profit"] or 0.0), 2)
        operating_expenses = round(float(metrics["operating_expenses"] or 0.0), 2)
        expenses_total = round(float(metrics["expenses"] or 0.0), 2)
        net_income = round(float(metrics["net_income"] or 0.0), 2)
        assets_total = round(cash + bank_accounts + recoverable_tax + inventory, 2)
        equity_total = round(assets_total - liabilities_total, 2)
        liabilities_and_equity = round(liabilities_total + equity_total, 2)
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
                    "short_term_loans": short_term_loans,
                    "tax_payable": tax_payable,
                    "total": liabilities_total,
                },
                "equity": {
                    "current_earnings": net_income,
                    "total": equity_total,
                },
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
                "financial_expenses": financial_expenses,
                "other_expenses": other_expenses,
                "operating_expenses": operating_expenses,
                "expenses": expenses_total,
                "net_income": net_income,
                "cmv": cmv,
                "gross_profit": gross_profit,
                "return_rate_pct": metrics["return_rate_pct"],
                "gross_margin_pct": metrics["gross_margin_pct"],
                "net_margin_pct": metrics["net_margin_pct"],
                "expense_ratio_pct": metrics["expense_ratio_pct"],
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

        fetch_limit = max(int(limit) * 8, 200)

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
            customer_name,
            customer_cpf,
            customer_email,
            customer_segment,
            warehouse_id,
            warehouse_name,
            channel,
            channel_name,
            entry_category,
            sale_id,
            order_id,
            order_status,
            order_origin,
            payment_method,
            payment_installments,
            coupon_code,
            device_type,
            sales_region,
            freight_service,
            cart_items_count,
            cart_quantity,
            cart_gross_amount,
            cart_discount,
            cart_net_amount,
            sale_line_index,
            source_payload_hash,
            TIME_FORMAT("__time", 'yyyy-MM-dd HH:mm:ss.SSS') AS occurred_at,
            ingested_at,
            revision
        FROM "{self.datasource}"
        WHERE {where_clause}
        ORDER BY "__time" DESC
        LIMIT {fetch_limit}
        """.strip()

        rows = await self._query_rows(sql)
        if not rows:
            fallback_sql = f"""
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
                supplier_name,
                warehouse_id,
                warehouse_name,
                channel_name,
                entry_category,
                order_id,
                source_payload_hash,
                TIME_FORMAT("__time", 'yyyy-MM-dd HH:mm:ss.SSS') AS occurred_at,
                ingested_at,
                revision
            FROM "{self.datasource}"
            WHERE {where_clause}
            ORDER BY "__time" DESC
            LIMIT {fetch_limit}
            """.strip()
            rows = await self._query_rows(fallback_sql)
        if not isinstance(rows, list):
            return []
        normalized_rows = []
        for row in rows:
            normalized_rows.append(
                {
                    **row,
                    "supplier_id": self._optional_text(row.get("supplier_id")),
                    "supplier_name": self._optional_text(row.get("supplier_name")),
                    "customer_id": self._optional_text(row.get("customer_id")),
                    "customer_name": self._optional_text(row.get("customer_name")),
                    "customer_cpf": self._optional_text(row.get("customer_cpf")),
                    "customer_email": self._optional_text(row.get("customer_email")),
                    "customer_segment": self._optional_text(row.get("customer_segment")),
                    "channel": str(row.get("channel") or row.get("channel_name") or ""),
                    "channel_name": str(row.get("channel_name") or row.get("channel") or ""),
                    "sale_id": self._optional_text(row.get("sale_id")),
                    "order_id": str(row.get("order_id") or ""),
                    "order_status": self._optional_text(row.get("order_status")),
                    "order_origin": self._optional_text(row.get("order_origin")),
                    "payment_method": self._optional_text(row.get("payment_method")),
                    "payment_installments": int(row.get("payment_installments", 0) or 0),
                    "coupon_code": self._optional_text(row.get("coupon_code")),
                    "device_type": self._optional_text(row.get("device_type")),
                    "sales_region": self._optional_text(row.get("sales_region")),
                    "freight_service": self._optional_text(row.get("freight_service")),
                    "cart_items_count": int(row.get("cart_items_count", 0) or 0),
                    "cart_quantity": float(row.get("cart_quantity", 0.0) or 0.0),
                    "cart_gross_amount": float(row.get("cart_gross_amount", 0.0) or 0.0),
                    "cart_discount": float(row.get("cart_discount", 0.0) or 0.0),
                    "cart_net_amount": float(row.get("cart_net_amount", 0.0) or 0.0),
                    "sale_line_index": int(row.get("sale_line_index", 0) or 0),
                    "quantity": float(row.get("quantity", 0.0) or 0.0),
                    "unit_price": float(row.get("unit_price", 0.0) or 0.0),
                    "amount": float(row.get("amount", 0.0) or 0.0),
                    "signed_amount": float(row.get("signed_amount", 0.0) or 0.0),
                }
            )
        return sorted(
            normalized_rows,
            key=lambda item: str(item.get("occurred_at") or ""),
            reverse=True,
        )[: int(limit)]

    async def _distinct(self, field: str) -> list[str]:
        sql = f"""
        SELECT {field} AS value
        FROM "{self.datasource}"
        WHERE {field} IS NOT NULL AND {field} != 'null' AND {field} != ''
        GROUP BY {field}
        ORDER BY {field}
        LIMIT 2000
        """.strip()
        rows = await self._query_rows(sql)
        return [str(item.get("value")) for item in rows if item.get("value") is not None]

    @staticmethod
    def _unique_values(rows: list[dict[str, Any]], field: str) -> list[str]:
        values = {
            str(row.get(field)).strip()
            for row in rows
            if row.get(field) not in (None, "", "null") and str(row.get(field)).strip()
        }
        return sorted(values)

    async def _recent_filter_seed(self, limit: int = 5000) -> list[dict[str, Any]]:
        return await self.get_recent_entries(limit=limit)

    async def get_filter_options(self) -> dict[str, list[str]]:
        options = {
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
            "payment_methods": await self._distinct("payment_method"),
            "order_statuses": await self._distinct("order_status"),
            "customer_segments": await self._distinct("customer_segment"),
        }

        if all(len(values) > 0 for values in options.values()):
            return options

        seed_rows = await self._recent_filter_seed()
        fallback_map = {
            "product_names": "product_name",
            "product_categories": "product_category",
            "supplier_names": "supplier_name",
            "event_types": "ontology_event_type",
            "entry_categories": "entry_category",
            "account_codes": "account_code",
            "warehouse_ids": "warehouse_id",
            "channels": "channel_name",
            "entry_sides": "entry_side",
            "ontology_sources": "ontology_source",
            "payment_methods": "payment_method",
            "order_statuses": "order_status",
            "customer_segments": "customer_segment",
        }

        for option_key, row_field in fallback_map.items():
            if options[option_key]:
                continue
            options[option_key] = self._unique_values(seed_rows, row_field)

        return options

    async def search_filter_values(self, field: str, query: str, limit: int = 20) -> list[str]:
        field_map = {
            "customer_name": "customer_name",
            "customer_cpf": "customer_cpf",
            "customer_email": "customer_email",
            "customer_id": "customer_id",
            "order_id": "order_id",
            "sale_id": "sale_id",
        }
        column = field_map.get(field)
        normalized_query = query.strip()
        if not column or not normalized_query:
            return []
        escaped = self._escape(normalized_query.lower())
        sql = f"""
        SELECT {column} AS value
        FROM "{self.datasource}"
        WHERE {column} IS NOT NULL
            AND {column} != 'null'
            AND {column} != ''
            AND LOWER({column}) LIKE '%{escaped}%'
        GROUP BY {column}
        ORDER BY {column}
        LIMIT {int(limit)}
        """.strip()
        rows = await self._query_rows(sql)
        matches = [str(item.get("value")) for item in rows if item.get("value")]
        if matches:
            return matches

        seed_rows = await self._recent_filter_seed()
        normalized_query_lower = normalized_query.lower()
        fallback_matches = []
        seen: set[str] = set()
        for row in seed_rows:
            raw_value = row.get(column)
            if raw_value in (None, "", "null"):
                continue
            value = str(raw_value).strip()
            normalized_value = value.lower()
            if normalized_query_lower not in normalized_value or value in seen:
                continue
            seen.add(value)
            fallback_matches.append(value)
            if len(fallback_matches) >= int(limit):
                break
        return fallback_matches

    async def _get_sales_workspace_fallback(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        where_clause = self._build_where(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at)
        sales_where_clause = f"{where_clause} AND ontology_event_type = 'sale' AND order_id != 'null' AND order_id != ''"

        sales_sql = f"""
        SELECT
            order_id,
            MAX(TIME_FORMAT("__time", 'yyyy-MM-dd HH:mm:ss.SSS')) AS occurred_at,
            MAX(product_name) AS lead_product,
            COUNT(DISTINCT product_name) AS product_mix,
            MAX(channel_name) AS channel_name,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN quantity ELSE 0 END), 3) AS quantity,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS gross_amount,
            ROUND(SUM(CASE WHEN account_role = 'cogs' THEN amount ELSE 0 END), 2) AS cmv,
            ROUND(SUM(CASE WHEN account_role = 'tax_payable' THEN amount ELSE 0 END), 2) AS tax_amount,
            ROUND(SUM(CASE WHEN account_role = 'marketplace_fees' THEN amount ELSE 0 END), 2) AS marketplace_fee_amount
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        GROUP BY order_id
        ORDER BY occurred_at DESC
        LIMIT 40
        """.strip()

        kpi_sql = f"""
        SELECT
            COUNT(DISTINCT order_id) AS order_count,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS gross_sales,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS net_sales,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END) - SUM(CASE WHEN account_role = 'cogs' THEN amount ELSE 0 END), 2) AS gross_margin,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN quantity ELSE 0 END), 3) AS units_sold,
            ROUND(AVG(CASE WHEN account_role = 'revenue' THEN quantity ELSE NULL END), 2) AS avg_items_per_order
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        """.strip()

        channel_sql = f"""
        SELECT
            channel_name AS label,
            COUNT(DISTINCT order_id) AS order_count,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN quantity ELSE 0 END), 3) AS quantity,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS gross_sales,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS net_sales
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        GROUP BY channel_name
        ORDER BY gross_sales DESC
        LIMIT 8
        """.strip()

        product_sql = f"""
        SELECT
            product_name AS label,
            COUNT(DISTINCT order_id) AS order_count,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN quantity ELSE 0 END), 3) AS quantity,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS gross_sales,
            ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS net_sales
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        GROUP BY product_name
        ORDER BY gross_sales DESC
        LIMIT 8
        """.strip()

        sales_rows, kpi_rows, by_channel, by_product = await asyncio.gather(
            self._query_rows(sales_sql),
            self._query_rows(kpi_sql),
            self._query_rows(channel_sql),
            self._query_rows(product_sql),
        )
        kpis = kpi_rows[0] if kpi_rows else {}
        order_count = int(kpis.get("order_count", 0) or 0)
        gross_sales = round(float(kpis.get("gross_sales", 0.0) or 0.0), 2)

        sales = [
            {
                "sale_id": str(row.get("order_id") or ""),
                "order_id": str(row.get("order_id") or ""),
                "occurred_at": row.get("occurred_at"),
                "customer_id": None,
                "customer_name": None,
                "customer_cpf": None,
                "customer_email": None,
                "customer_segment": None,
                "channel": str(row.get("channel_name") or ""),
                "channel_name": str(row.get("channel_name") or ""),
                "payment_method": None,
                "payment_installments": 0,
                "order_status": None,
                "order_origin": None,
                "coupon_code": None,
                "device_type": None,
                "sales_region": None,
                "freight_service": None,
                "lead_product": row.get("lead_product"),
                "product_mix": int(row.get("product_mix", 1) or 1),
                "cart_items_count": int(row.get("product_mix", 1) or 1),
                "quantity": round(float(row.get("quantity", 0.0) or 0.0), 3),
                "gross_amount": round(float(row.get("gross_amount", 0.0) or 0.0), 2),
                "net_amount": round(float(row.get("gross_amount", 0.0) or 0.0), 2),
                "cart_discount": 0.0,
                "tax_amount": round(float(row.get("tax_amount", 0.0) or 0.0), 2),
                "marketplace_fee_amount": round(float(row.get("marketplace_fee_amount", 0.0) or 0.0), 2),
                "cmv": round(float(row.get("cmv", 0.0) or 0.0), 2),
            }
            for row in sales_rows
        ]

        return {
            "sales": sales,
            "kpis": {
                "order_count": order_count,
                "unique_customers": 0,
                "gross_sales": gross_sales,
                "net_sales": gross_sales,
                "units_sold": round(float(kpis.get("units_sold", 0.0) or 0.0), 3),
                "average_ticket": round(gross_sales / order_count, 2) if order_count else 0.0,
                "avg_items_per_order": round(float(kpis.get("avg_items_per_order", 0.0) or 0.0), 2),
                "gross_margin": round(float(kpis.get("gross_margin", 0.0) or 0.0), 2),
            },
            "by_channel": by_channel,
            "by_product": by_product,
            "by_status": [],
            "by_payment": [],
            "data_mode": "pinot_order_fallback",
            "data_warning": "Druid ainda nao materializou sale_id, customer_*, payment_method e order_status neste conjunto. O painel comercial foi degradado para um modo seguro por pedido, produto, canal, quantidade e receita enquanto a leitura detalhada e estabilizada.",
            "missing_dimensions": ["sale_id", "customer_name", "customer_email", "customer_segment", "payment_method", "order_status"],
        }

    async def get_sales_workspace(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        where_clause = self._build_where(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at)
        sales_where_clause = f"{where_clause} AND ontology_event_type = 'sale' AND account_role = 'revenue'"

        sales_sql = f"""
        SELECT
            sale_id,
            ANY_VALUE(order_id) AS order_id,
            TIME_FORMAT(MAX("__time"), 'yyyy-MM-dd HH:mm:ss.SSS') AS occurred_at,
            ANY_VALUE(customer_id) AS customer_id,
            ANY_VALUE(customer_name) AS customer_name,
            ANY_VALUE(customer_cpf) AS customer_cpf,
            ANY_VALUE(customer_email) AS customer_email,
            ANY_VALUE(customer_segment) AS customer_segment,
            ANY_VALUE(channel) AS channel,
            ANY_VALUE(channel_name) AS channel_name,
            ANY_VALUE(payment_method) AS payment_method,
            MAX(payment_installments) AS payment_installments,
            ANY_VALUE(order_status) AS order_status,
            ANY_VALUE(order_origin) AS order_origin,
            ANY_VALUE(coupon_code) AS coupon_code,
            ANY_VALUE(device_type) AS device_type,
            ANY_VALUE(sales_region) AS sales_region,
            ANY_VALUE(freight_service) AS freight_service,
            ANY_VALUE(product_name) AS lead_product,
            COUNT(DISTINCT product_id) AS product_mix,
            MAX(cart_items_count) AS cart_items_count,
            ROUND(SUM(quantity), 3) AS quantity,
            ROUND(SUM(gross_amount), 2) AS gross_amount,
            ROUND(SUM(net_amount), 2) AS net_amount,
            MAX(cart_discount) AS cart_discount,
            ROUND(SUM(tax_amount), 2) AS tax_amount,
            ROUND(SUM(marketplace_fee_amount), 2) AS marketplace_fee_amount,
            ROUND(SUM(inventory_cost_total), 2) AS cmv
        FROM "{self.datasource}"
        WHERE {sales_where_clause} AND sale_id IS NOT NULL AND sale_id != 'null' AND sale_id != ''
        GROUP BY sale_id
        ORDER BY occurred_at DESC
        LIMIT 40
        """.strip()

        kpi_sql = f"""
        SELECT
            COUNT(DISTINCT sale_id) AS order_count,
            COUNT(DISTINCT COALESCE(customer_email, customer_id, sale_id)) AS unique_customers,
            ROUND(SUM(gross_amount), 2) AS gross_sales,
            ROUND(SUM(net_amount), 2) AS net_sales,
            ROUND(SUM(net_amount - inventory_cost_total), 2) AS gross_margin,
            ROUND(SUM(quantity), 3) AS units_sold,
            ROUND(AVG(cart_items_count), 2) AS avg_items_per_order
        FROM "{self.datasource}"
        WHERE {sales_where_clause} AND sale_id IS NOT NULL AND sale_id != 'null' AND sale_id != ''
        """.strip()

        channel_sql = f"""
        SELECT
            channel_name AS label,
            COUNT(DISTINCT sale_id) AS order_count,
            ROUND(SUM(quantity), 3) AS quantity,
            ROUND(SUM(gross_amount), 2) AS gross_sales,
            ROUND(SUM(net_amount), 2) AS net_sales
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        GROUP BY channel_name
        ORDER BY net_sales DESC
        LIMIT 8
        """.strip()

        product_sql = f"""
        SELECT
            product_name AS label,
            COUNT(DISTINCT sale_id) AS order_count,
            ROUND(SUM(quantity), 3) AS quantity,
            ROUND(SUM(gross_amount), 2) AS gross_sales,
            ROUND(SUM(net_amount), 2) AS net_sales
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        GROUP BY product_name
        ORDER BY net_sales DESC
        LIMIT 8
        """.strip()

        status_sql = f"""
        SELECT
            order_status AS label,
            COUNT(DISTINCT sale_id) AS order_count,
            ROUND(SUM(net_amount), 2) AS net_sales
        FROM "{self.datasource}"
        WHERE {sales_where_clause} AND order_status IS NOT NULL AND order_status != 'null' AND order_status != ''
        GROUP BY order_status
        ORDER BY order_count DESC
        LIMIT 6
        """.strip()

        payment_sql = f"""
        SELECT
            payment_method AS label,
            COUNT(DISTINCT sale_id) AS order_count,
            ROUND(SUM(quantity), 3) AS quantity,
            ROUND(SUM(gross_amount), 2) AS gross_sales,
            ROUND(SUM(net_amount), 2) AS net_sales
        FROM "{self.datasource}"
        WHERE {sales_where_clause}
        GROUP BY payment_method
        ORDER BY net_sales DESC
        LIMIT 12
        """.strip()

        sales, kpi_rows, by_channel, by_product, by_status, by_payment_rows = await asyncio.gather(
            self._query_rows(sales_sql),
            self._query_rows(kpi_sql),
            self._query_rows(channel_sql),
            self._query_rows(product_sql),
            self._query_rows(status_sql),
            self._query_rows(payment_sql),
        )
        kpis = kpi_rows[0] if kpi_rows else {}
        order_count = int(kpis.get("order_count", 0) or 0)
        net_sales = round(float(kpis.get("net_sales", 0.0) or 0.0), 2)
        by_payment = self._normalize_breakdown_rows(by_payment_rows)[:8]
        result = {
            "sales": sales,
            "kpis": {
                "order_count": order_count,
                "unique_customers": int(kpis.get("unique_customers", 0) or 0),
                "gross_sales": round(float(kpis.get("gross_sales", 0.0) or 0.0), 2),
                "net_sales": net_sales,
                "units_sold": round(float(kpis.get("units_sold", 0.0) or 0.0), 3),
                "average_ticket": round(net_sales / order_count, 2) if order_count else 0.0,
                "avg_items_per_order": round(float(kpis.get("avg_items_per_order", 0.0) or 0.0), 2),
                "gross_margin": round(float(kpis.get("gross_margin", 0.0) or 0.0), 2),
            },
            "by_channel": by_channel,
            "by_product": by_product,
            "by_status": by_status,
            "by_payment": by_payment,
            "data_mode": "full",
            "data_warning": None,
            "missing_dimensions": [],
        }
        if order_count == 0 and not sales:
            return await self._get_sales_workspace_fallback(as_of=as_of, start_at=start_at, end_at=end_at, filters=filters)
        return result

    async def get_master_data_overview(self) -> dict[str, Any]:
        health, company, products, accounts, channels = await asyncio.gather(
            self._fetch_json("/health", {}),
            self._fetch_json("/api/v1/master-data/company", {}),
            self._fetch_json("/api/v1/master-data/products", []),
            self._fetch_json("/api/v1/master-data/accounts", []),
            self._fetch_json("/api/v1/master-data/channels", []),
        )
        counts = health.get("counts") if isinstance(health, dict) else {}
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
            self._query_rows(
                f"""
                SELECT
                    account_code,
                    ROUND(SUM(signed_amount), 2) AS current_balance,
                    COUNT(*) AS entry_count
                FROM "{self.datasource}"
                WHERE is_current = 1
                GROUP BY account_code
                ORDER BY account_code
                LIMIT 500
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
            self._query_rows(
                f"""
                SELECT
                    product_id,
                    ROUND(SUM(CASE WHEN account_role = 'inventory' AND (order_id IS NULL OR order_id NOT LIKE 'BOOT-%') THEN CASE WHEN entry_side = 'debit' THEN quantity ELSE 0 - quantity END ELSE 0 END), 3) AS stock_delta_quantity,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN quantity ELSE 0 END), 3) AS sold_quantity,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'return' AND account_role = 'inventory' THEN quantity ELSE 0 END), 3) AS returned_quantity,
                    ROUND(SUM(CASE WHEN account_role = 'revenue' THEN amount ELSE 0 END), 2) AS revenue_amount,
                    ROUND(SUM(CASE WHEN account_role = 'returns' THEN amount ELSE 0 END), 2) AS return_amount,
                    ROUND(SUM(CASE WHEN account_role = 'cogs' THEN signed_amount ELSE 0 END), 2) AS cogs_amount,
                    ROUND(SUM(CASE WHEN account_role = 'marketplace_fees' THEN signed_amount ELSE 0 END), 2) AS marketplace_fees_amount,
                    ROUND(SUM(CASE WHEN account_role = 'outbound_freight' THEN signed_amount ELSE 0 END), 2) AS freight_out_amount,
                    ROUND(SUM(CASE WHEN account_role = 'bank_fees' THEN signed_amount ELSE 0 END), 2) AS bank_fees_amount,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'purchase' AND account_role = 'inventory' THEN unit_price ELSE 0 END), 2) AS purchase_price_sum,
                    SUM(CASE WHEN ontology_event_type = 'purchase' AND account_role = 'inventory' THEN 1 ELSE 0 END) AS purchase_event_count,
                    ROUND(SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN unit_price ELSE 0 END), 2) AS sale_price_sum,
                    SUM(CASE WHEN ontology_event_type = 'sale' AND account_role = 'inventory' THEN 1 ELSE 0 END) AS sale_event_count
                FROM "{self.datasource}"
                WHERE is_current = 1 AND product_id IS NOT NULL AND product_id != 'null' AND product_id != ''
                GROUP BY product_id
                ORDER BY product_id
                LIMIT 2000
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
            stock_delta_quantity = float(aggregate.get("stock_delta_quantity", 0.0) or 0.0)
            stock_quantity = round(max(opening_stock_quantity + stock_delta_quantity, 0.0), 3)
            sold_quantity = round(float(aggregate.get("sold_quantity", 0.0)), 3)
            returned_quantity = round(float(aggregate.get("returned_quantity", 0.0)), 3)
            net_sold_quantity = round(max(sold_quantity - returned_quantity, 0.0), 3)
            revenue_amount = round(float(aggregate.get("revenue_amount", 0.0)), 2)
            return_amount = round(float(aggregate.get("return_amount", 0.0)), 2)
            net_revenue_amount = round(revenue_amount - return_amount, 2)
            cogs_amount = round(float(aggregate.get("cogs_amount", 0.0)), 2)
            marketplace_fees_amount = round(float(aggregate.get("marketplace_fees_amount", 0.0)), 2)
            freight_out_amount = round(float(aggregate.get("freight_out_amount", 0.0)), 2)
            bank_fees_amount = round(float(aggregate.get("bank_fees_amount", 0.0)), 2)
            selling_expenses_amount = round(marketplace_fees_amount + freight_out_amount + bank_fees_amount, 2)
            gross_profit_amount = round(net_revenue_amount - cogs_amount, 2)
            net_profit_amount = round(gross_profit_amount - selling_expenses_amount, 2)
            supply_plan = self._supply_plan(product, stock_quantity, net_sold_quantity)
            rows.append(
                {
                    **product,
                    "registered_channels": [channel_map.get(channel_id, channel_id) for channel_id in product.get("channel_ids", [])],
                    "opening_stock_quantity": opening_stock_quantity,
                    "current_stock_quantity": stock_quantity,
                    "sold_quantity": sold_quantity,
                    "net_sold_quantity": net_sold_quantity,
                    "returned_quantity": returned_quantity,
                    "average_purchase_price": average_purchase_price,
                    "average_sale_price": average_sale_price,
                    "revenue_amount": revenue_amount,
                    "return_amount": return_amount,
                    "net_revenue_amount": net_revenue_amount,
                    "cogs_amount": cogs_amount,
                    "selling_expenses_amount": selling_expenses_amount,
                    "gross_profit_amount": gross_profit_amount,
                    "net_profit_amount": net_profit_amount,
                    "return_rate_pct": self._percentage(returned_quantity, sold_quantity),
                    "gross_margin_pct": self._percentage(gross_profit_amount, net_revenue_amount),
                    "net_margin_pct": self._percentage(net_profit_amount, net_revenue_amount),
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
        summary, entries, master_data, accounts, products, sales_workspace = await asyncio.gather(
            self.get_summary(as_of=as_of, start_at=start_at, end_at=end_at, filters=filters),
            self.get_recent_entries(limit=180, as_of=as_of, start_at=start_at, end_at=end_at, filters=filters),
            self.get_master_data_overview(),
            self.get_account_catalog(),
            self.get_product_catalog(),
            self.get_sales_workspace(as_of=as_of, start_at=start_at, end_at=end_at, filters=filters),
        )
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "entries": entries,
            "master_data": master_data,
            "account_catalog": accounts,
            "product_catalog": products,
            "sales_workspace": sales_workspace,
        }
