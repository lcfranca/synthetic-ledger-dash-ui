import asyncio
import json
import os
from datetime import datetime, timezone
from typing import Any

import httpx


class DashboardRepository:
    def __init__(self) -> None:
        self.base_url = os.getenv("CLICKHOUSE_URL", "http://clickhouse:8123")
        self.db = os.getenv("CLICKHOUSE_DB", "ledger")
        self.table = f"{self.db}.entries"
        self.user = os.getenv("CLICKHOUSE_USER", "ledger_app")
        self.password = os.getenv("CLICKHOUSE_PASSWORD", "ledger_app_pass")
        self.master_data_url = os.getenv("MASTER_DATA_URL", "http://master-data:8091")
        clickhouse_timeout = httpx.Timeout(connect=2.5, read=20.0, write=20.0, pool=20.0)
        clickhouse_limits = httpx.Limits(max_connections=64, max_keepalive_connections=16)
        master_data_timeout = httpx.Timeout(connect=2.5, read=8.0, write=8.0, pool=8.0)
        master_data_limits = httpx.Limits(max_connections=16, max_keepalive_connections=8)
        self.clickhouse_client = httpx.AsyncClient(timeout=clickhouse_timeout, limits=clickhouse_limits)
        self.master_data_client = httpx.AsyncClient(timeout=master_data_timeout, limits=master_data_limits)
        self.clickhouse_query_semaphore = asyncio.Semaphore(int(os.getenv("CLICKHOUSE_MAX_CONCURRENT_QUERIES", "12")))

    async def _post_clickhouse(self, sql: str) -> httpx.Response:
        async with self.clickhouse_query_semaphore:
            response = await self.clickhouse_client.post(
                f"{self.base_url}/",
                params={"database": self.db, "query": sql},
                auth=(self.user, self.password),
            )
        response.raise_for_status()
        return response

    @staticmethod
    def _escape(value: str) -> str:
        return value.replace("'", "''")

    @staticmethod
    def _optional_text(value: Any) -> str | None:
        if value in (None, "", "null"):
            return None
        return str(value)

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

    def _build_filters(
        self,
        filters: dict[str, str | None],
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
    ) -> str:
        clauses = ["is_current = 1"]

        if start_at:
            normalized_start_at = start_at.replace("T", " ").replace("+00:00", "")
            clauses.append(f"occurred_at >= parseDateTime64BestEffort('{self._escape(normalized_start_at)}', 3)")

        upper_bound = end_at or as_of
        if upper_bound:
            normalized_upper_bound = upper_bound.replace("T", " ").replace("+00:00", "")
            clauses.append(f"occurred_at <= parseDateTime64BestEffort('{self._escape(normalized_upper_bound)}', 3)")

        for field, value in filters.items():
            if not value:
                continue
            normalized_value = self._escape(value.strip())
            if not normalized_value:
                continue
            clauses.append(f"{field} = '{normalized_value}'")

        return " AND ".join(clauses)

    async def _query(self, sql: str) -> str:
        try:
            response = await self._post_clickhouse(sql)
            return response.text.strip()
        except httpx.HTTPStatusError as exc:
            if self._is_missing_table_error(exc):
                return ""
            raise

    async def _query_json_rows(self, sql: str) -> list[dict[str, Any]]:
        try:
            response = await self._post_clickhouse(sql)
            lines = [line.strip() for line in response.text.splitlines() if line.strip()]
            return [json.loads(line) for line in lines]
        except httpx.HTTPStatusError as exc:
            if self._is_missing_table_error(exc):
                return []
            raise

    async def _query_json_row(self, sql: str) -> dict[str, Any]:
        rows = await self._query_json_rows(sql)
        return rows[0] if rows else {}

    @staticmethod
    def _is_missing_table_error(exc: httpx.HTTPStatusError) -> bool:
        if exc.response.status_code != 404:
            return False
        message = exc.response.text or ""
        return "UNKNOWN_TABLE" in message or "does not exist" in message or not message

    async def _fetch_json(self, path: str, default: Any) -> Any:
        try:
            response = await self.master_data_client.get(f"{self.master_data_url}{path}")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, type(default)) else default
        except Exception:
            return default

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

    async def get_summary(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        cutoff = end_at or as_of or datetime.now(timezone.utc).isoformat().replace("T", " ").replace("+00:00", "")
        where_clause = self._build_filters(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at or cutoff)
        sql = f"""
        SELECT
            round(sumIf(signed_amount, account_role = 'cash'), 2) AS cash,
            round(sumIf(signed_amount, account_role = 'bank_accounts'), 2) AS bank_accounts,
            round(sumIf(signed_amount, account_role = 'recoverable_tax'), 2) AS recoverable_tax,
            round(sumIf(signed_amount, account_role = 'inventory'), 2) AS inventory,
            round(abs(sumIf(signed_amount, account_role = 'accounts_payable')), 2) AS accounts_payable,
            round(abs(sumIf(signed_amount, account_role = 'short_term_loans')), 2) AS short_term_loans,
            round(abs(sumIf(signed_amount, account_role = 'tax_payable')), 2) AS tax_payable,
            round(abs(sumIf(signed_amount, account_role = 'revenue')), 2) AS revenue,
            round(sumIf(signed_amount, account_role = 'returns'), 2) AS returns,
            round(sumIf(signed_amount, account_role = 'marketplace_fees'), 2) AS marketplace_fees,
            round(sumIf(signed_amount, account_role = 'outbound_freight'), 2) AS freight_out,
            round(sumIf(signed_amount, account_role = 'bank_fees'), 2) AS bank_fees,
            round(sumIf(signed_amount, account_role = 'interest_expense'), 2) AS financial_expenses,
            round(sumIf(signed_amount, account_role = 'cogs'), 2) AS cmv,
            round(sumIf(signed_amount, statement_section = 'expense' AND account_role NOT IN ('cogs', 'marketplace_fees', 'outbound_freight', 'bank_fees', 'interest_expense')), 2) AS other_expenses
        FROM ledger.entries
        WHERE {where_clause}
        """.strip()

        raw = await self._query(sql)
        values = [float(part) if part else 0.0 for part in raw.split("\t")]
        while len(values) < 15:
            values.append(0.0)

        (
            cash,
            bank_accounts,
            recoverable_tax,
            inventory,
            accounts_payable,
            short_term_loans,
            tax_payable,
            revenue,
            returns,
            marketplace_fees,
            freight_out,
            bank_fees,
            financial_expenses,
            cmv,
            other_expenses,
        ) = values[:15]
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
                "equity": {"current_earnings": net_income, "total": equity_total},
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
        where_clause = self._build_filters(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at)

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
            occurred_at,
            ingested_at,
            revision
        FROM ledger.entries
        WHERE {where_clause}
        ORDER BY occurred_at DESC
        LIMIT {fetch_limit}
        FORMAT JSONEachRow
        """.strip()

        rows = await self._query_json_rows(sql)
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

        return sorted(normalized_rows, key=lambda item: str(item.get("occurred_at") or ""), reverse=True)[: int(limit)]

    async def get_filter_options(self) -> dict[str, list[str]]:
        sql = """
        SELECT
            groupUniqArrayIf(product_name, product_name != '' AND product_name != 'null') AS product_names,
            groupUniqArrayIf(product_category, product_category != '' AND product_category != 'null') AS product_categories,
            groupUniqArrayIf(supplier_name, supplier_name IS NOT NULL AND supplier_name != '' AND supplier_name != 'null') AS supplier_names,
            groupUniqArrayIf(ontology_event_type, ontology_event_type != '' AND ontology_event_type != 'null') AS event_types,
            groupUniqArrayIf(entry_category, entry_category != '' AND entry_category != 'null') AS entry_categories,
            groupUniqArrayIf(account_code, account_code != '' AND account_code != 'null') AS account_codes,
            groupUniqArrayIf(warehouse_id, warehouse_id != '' AND warehouse_id != 'null') AS warehouse_ids,
            groupUniqArrayIf(channel_name, channel_name != '' AND channel_name != 'null') AS channels,
            groupUniqArrayIf(entry_side, entry_side != '' AND entry_side != 'null') AS entry_sides,
            groupUniqArrayIf(ontology_source, ontology_source != '' AND ontology_source != 'null') AS ontology_sources,
            groupUniqArrayIf(payment_method, payment_method IS NOT NULL AND payment_method != '' AND payment_method != 'null') AS payment_methods,
            groupUniqArrayIf(order_status, order_status IS NOT NULL AND order_status != '' AND order_status != 'null') AS order_statuses,
            groupUniqArrayIf(customer_segment, customer_segment IS NOT NULL AND customer_segment != '' AND customer_segment != 'null') AS customer_segments
        FROM ledger.entries
        WHERE is_current = 1
        FORMAT JSONEachRow
        """.strip()

        response = await self._post_clickhouse(sql)

        line = next((item for item in response.text.splitlines() if item.strip()), "{}")
        payload = json.loads(line)
        return {key: sorted(set(value or [])) for key, value in payload.items()}

    async def search_filter_values(self, field: str, query: str, limit: int = 20) -> list[str]:
        field_map = {
            "customer_name": "customer_name",
            "customer_cpf": "customer_cpf",
            "customer_email": "customer_email",
            "customer_id": "customer_id",
            "order_id": "order_id",
            "sale_id": "sale_id",
            "payment_method": "payment_method",
            "order_status": "order_status",
            "product_name": "product_name",
            "supplier_name": "supplier_name",
        }
        column = field_map.get(field)
        normalized_query = query.strip()
        if not column or not normalized_query:
            return []
        escaped_query = self._escape(normalized_query)
        sql = f"""
        SELECT DISTINCT {column} AS value
        FROM ledger.entries
        WHERE is_current = 1
            AND {column} IS NOT NULL
            AND {column} != 'null'
            AND {column} != ''
            AND positionCaseInsensitive({column}, '{escaped_query}') > 0
        ORDER BY value
        LIMIT {int(limit)}
        FORMAT JSONEachRow
        """.strip()
        rows = await self._query_json_rows(sql)
        return [str(item.get("value")) for item in rows if item.get("value")]

    async def get_sales_workspace(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        where_clause = self._build_filters(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at)
        sales_where_clause = f"{where_clause} AND ontology_event_type = 'sale' AND account_role = 'revenue'"

        sales_sql = f"""
        SELECT
            sale_id,
            any(order_id) AS order_id,
            max(occurred_at) AS occurred_at,
            any(customer_id) AS customer_id,
            any(customer_name) AS customer_name,
            any(customer_cpf) AS customer_cpf,
            any(customer_email) AS customer_email,
            any(customer_segment) AS customer_segment,
            any(channel) AS channel,
            any(channel_name) AS channel_name,
            any(payment_method) AS payment_method,
            max(payment_installments) AS payment_installments,
            any(order_status) AS order_status,
            any(order_origin) AS order_origin,
            any(coupon_code) AS coupon_code,
            any(device_type) AS device_type,
            any(sales_region) AS sales_region,
            any(freight_service) AS freight_service,
            any(product_name) AS lead_product,
            uniqExact(product_id) AS product_mix,
            max(cart_items_count) AS cart_items_count,
            round(sum(quantity), 3) AS quantity,
            round(sum(gross_amount), 2) AS gross_amount,
            round(sum(net_amount), 2) AS net_amount,
            max(cart_discount) AS cart_discount,
            round(sum(tax_amount), 2) AS tax_amount,
            round(sum(marketplace_fee_amount), 2) AS marketplace_fee_amount,
            round(sum(inventory_cost_total), 2) AS cmv
        FROM ledger.entries
        WHERE {sales_where_clause} AND sale_id IS NOT NULL AND sale_id != ''
        GROUP BY sale_id
        ORDER BY occurred_at DESC
        LIMIT 40
        FORMAT JSONEachRow
        """.strip()

        kpi_sql = f"""
        SELECT
            uniqExact(sale_id) AS order_count,
            uniqExact(ifNull(customer_email, ifNull(customer_id, sale_id))) AS unique_customers,
            round(sum(gross_amount), 2) AS gross_sales,
            round(sum(net_amount), 2) AS net_sales,
            round(sum(quantity), 3) AS units_sold,
            round(avg(cart_items_count), 2) AS avg_items_per_order
        FROM ledger.entries
        WHERE {sales_where_clause} AND sale_id IS NOT NULL AND sale_id != ''
        FORMAT JSONEachRow
        """.strip()

        channel_sql = f"""
        SELECT
            channel_name AS label,
            uniqExact(sale_id) AS order_count,
            round(sum(quantity), 3) AS quantity,
            round(sum(gross_amount), 2) AS gross_sales,
            round(sum(net_amount), 2) AS net_sales
        FROM ledger.entries
        WHERE {sales_where_clause}
        GROUP BY channel_name
        ORDER BY net_sales DESC
        LIMIT 8
        FORMAT JSONEachRow
        """.strip()

        product_sql = f"""
        SELECT
            product_name AS label,
            uniqExact(sale_id) AS order_count,
            round(sum(quantity), 3) AS quantity,
            round(sum(gross_amount), 2) AS gross_sales,
            round(sum(net_amount), 2) AS net_sales
        FROM ledger.entries
        WHERE {sales_where_clause}
        GROUP BY product_name
        ORDER BY net_sales DESC
        LIMIT 8
        FORMAT JSONEachRow
        """.strip()

        status_sql = f"""
        SELECT
            order_status AS label,
            uniqExact(sale_id) AS order_count,
            round(sum(net_amount), 2) AS net_sales
        FROM ledger.entries
        WHERE {sales_where_clause} AND order_status IS NOT NULL AND order_status != ''
        GROUP BY order_status
        ORDER BY order_count DESC
        LIMIT 6
        FORMAT JSONEachRow
        """.strip()

        payment_sql = f"""
        SELECT
            payment_method AS label,
            uniqExact(sale_id) AS order_count,
            round(sum(quantity), 3) AS quantity,
            round(sum(gross_amount), 2) AS gross_sales,
            round(sum(net_amount), 2) AS net_sales
        FROM ledger.entries
        WHERE {sales_where_clause} AND payment_method IS NOT NULL AND payment_method != '' AND payment_method != 'null'
        GROUP BY payment_method
        ORDER BY net_sales DESC
        LIMIT 12
        FORMAT JSONEachRow
        """.strip()

        try:
            sales, kpis, by_channel, by_product, by_status, by_payment_rows = await asyncio.gather(
                self._query_json_rows(sales_sql),
                self._query_json_row(kpi_sql),
                self._query_json_rows(channel_sql),
                self._query_json_rows(product_sql),
                self._query_json_rows(status_sql),
                self._query_json_rows(payment_sql),
            )
        except Exception:
            return {
                "sales": [],
                "kpis": {
                    "order_count": 0,
                    "unique_customers": 0,
                    "gross_sales": 0.0,
                    "net_sales": 0.0,
                    "units_sold": 0.0,
                    "average_ticket": 0.0,
                    "avg_items_per_order": 0.0,
                    "gross_margin": 0.0,
                },
                "by_channel": [],
                "by_product": [],
                "by_status": [],
                "by_payment": [],
                "data_mode": "full",
                "data_warning": "sales_workspace_unavailable_for_current_filter",
                "missing_dimensions": ["sales_workspace"],
            }

        order_count = int(kpis.get("order_count", 0) or 0)
        net_sales = round(float(kpis.get("net_sales", 0.0) or 0.0), 2)
        by_payment = self._normalize_breakdown_rows(by_payment_rows)[:8]

        return {
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

    async def get_master_data_overview(self) -> dict[str, Any]:
        health, company, products, accounts, channels = await asyncio.gather(
            self._fetch_json("/health", {}),
            self._fetch_json("/api/v1/master-data/company", {}),
            self._fetch_json("/api/v1/master-data/products", []),
            self._fetch_json("/api/v1/master-data/accounts", []),
            self._fetch_json("/api/v1/master-data/channels", []),
        )
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
                    round(sum(signed_amount), 2) AS current_balance,
                    count() AS entry_count
                FROM ledger.entries
                WHERE is_current = 1
                GROUP BY account_code
                ORDER BY account_code
                LIMIT 500
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
                    round(sumIf(if(entry_side = 'debit', quantity, 0 - quantity), account_role = 'inventory' AND (isNull(order_id) OR order_id NOT LIKE 'BOOT-%')), 3) AS stock_delta_quantity,
                    round(sumIf(quantity, ontology_event_type = 'sale' AND account_role = 'inventory'), 3) AS sold_quantity,
                    round(sumIf(quantity, ontology_event_type = 'return' AND account_role = 'inventory'), 3) AS returned_quantity,
                    round(sumIf(amount, account_role = 'revenue'), 2) AS revenue_amount,
                    round(sumIf(amount, account_role = 'returns'), 2) AS return_amount,
                    round(sumIf(signed_amount, account_role = 'cogs'), 2) AS cogs_amount,
                    round(sumIf(signed_amount, account_role = 'marketplace_fees'), 2) AS marketplace_fees_amount,
                    round(sumIf(signed_amount, account_role = 'outbound_freight'), 2) AS freight_out_amount,
                    round(sumIf(signed_amount, account_role = 'bank_fees'), 2) AS bank_fees_amount,
                    round(sumIf(unit_price, ontology_event_type = 'purchase' AND account_role = 'inventory'), 2) AS purchase_price_sum,
                    countIf(ontology_event_type = 'purchase' AND account_role = 'inventory') AS purchase_event_count,
                    round(sumIf(unit_price, ontology_event_type = 'sale' AND account_role = 'inventory'), 2) AS sale_price_sum,
                    countIf(ontology_event_type = 'sale' AND account_role = 'inventory') AS sale_event_count
                FROM ledger.entries
                WHERE is_current = 1 AND product_id IS NOT NULL AND product_id != '' AND product_id != 'null'
                GROUP BY product_id
                ORDER BY product_id
                LIMIT 2000
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
