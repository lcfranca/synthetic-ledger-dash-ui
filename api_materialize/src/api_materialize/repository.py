import asyncio
import os
from datetime import datetime, timezone
from typing import Any

import httpx
import psycopg
from psycopg.rows import dict_row


class MaterializeQueryError(RuntimeError):
    pass


class DashboardRepository:
    def __init__(self) -> None:
        schema = os.getenv("MATERIALIZE_VIEW_SCHEMA", os.getenv("MATERIALIZE_SCHEMA", "public"))
        self.conninfo = os.getenv("MATERIALIZE_URL", "postgresql://materialize@materialized:6875/materialize")
        self.master_data_url = os.getenv("MASTER_DATA_URL", "http://master-data:8091")
        self.entries_view = f"{schema}.ledger_entries_current_mv"
        self.summary_view = f"{schema}.ledger_summary_by_role_mv"
        self.sales_view = f"{schema}.ledger_sales_mv"
        self.account_balances_view = f"{schema}.ledger_account_balances_mv"
        self.product_metrics_view = f"{schema}.ledger_product_metrics_mv"
        self.query_semaphore = asyncio.Semaphore(int(os.getenv("MATERIALIZE_MAX_CONCURRENT_QUERIES", "8") or 8))
        materialize_timeout = httpx.Timeout(connect=2.5, read=8.0, write=8.0, pool=8.0)
        materialize_limits = httpx.Limits(max_connections=16, max_keepalive_connections=8)
        self.master_data_client = httpx.AsyncClient(timeout=materialize_timeout, limits=materialize_limits)

    def _connect(self) -> psycopg.Connection[Any]:
        return psycopg.connect(self.conninfo, autocommit=True, row_factory=dict_row)

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

    def _run_query_sync(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)
                    rows = cursor.fetchall() or []
                    return [dict(row) for row in rows]
        except Exception as exc:
            raise MaterializeQueryError(str(exc)) from exc

    async def _query_rows(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        async with self.query_semaphore:
            return await asyncio.to_thread(self._run_query_sync, sql, params)

    async def _query_row(self, sql: str, params: tuple[Any, ...] = ()) -> dict[str, Any]:
        rows = await self._query_rows(sql, params)
        return rows[0] if rows else {}

    async def _fetch_json(self, path: str, default: Any) -> Any:
        try:
            response = await self.master_data_client.get(f"{self.master_data_url}{path}")
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, type(default)) else default
        except Exception:
            return default

    def _build_where(
        self,
        filters: dict[str, str | None],
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        alias: str = "",
    ) -> tuple[str, list[Any]]:
        prefix = f"{alias}." if alias else ""
        clauses = ["1 = 1"]
        params: list[Any] = []

        if start_at:
            clauses.append(f"{prefix}occurred_at >= %s")
            params.append(start_at)

        upper_bound = end_at or as_of
        if upper_bound:
            clauses.append(f"{prefix}occurred_at <= %s")
            params.append(upper_bound)

        for field, value in filters.items():
            if not value:
                continue
            normalized = value.strip()
            if not normalized:
                continue
            clauses.append(f"{prefix}{field} = %s")
            params.append(normalized)

        return " AND ".join(clauses), params

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

    async def get_query_layer_metrics(self) -> dict[str, Any]:
        row = await self._query_row(
            f"SELECT COUNT(*) AS hydrated_rows, MAX(occurred_at) AS max_occurred_at, MAX(ingested_at) AS max_ingested_at, MAX(kafka_offset) AS max_kafka_offset FROM {self.entries_view}"
        )
        hydrated_rows = int(row.get("hydrated_rows", 0) or 0)
        max_occurred_at = row.get("max_occurred_at")
        max_ingested_at = row.get("max_ingested_at")
        now = datetime.now(timezone.utc)
        freshness_ms = None
        view_lag_ms = None
        if isinstance(max_occurred_at, datetime):
            freshness_ms = max(int((now - max_occurred_at.astimezone(timezone.utc)).total_seconds() * 1000), 0)
        if isinstance(max_ingested_at, datetime):
            view_lag_ms = max(int((now - max_ingested_at.astimezone(timezone.utc)).total_seconds() * 1000), 0)
        return {
            "hydrated_rows": hydrated_rows,
            "last_occurred_at": max_occurred_at.astimezone(timezone.utc).isoformat() if isinstance(max_occurred_at, datetime) else None,
            "last_ingested_at": max_ingested_at.astimezone(timezone.utc).isoformat() if isinstance(max_ingested_at, datetime) else None,
            "last_kafka_offset": int(row.get("max_kafka_offset", 0) or 0),
            "view_lag_ms": view_lag_ms,
            "freshness_ms": freshness_ms,
        }

    async def get_summary(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        cutoff = end_at or as_of or datetime.now(timezone.utc).isoformat()
        active_filters = filters or {}
        if not any(active_filters.values()) and not start_at and not end_at and not as_of:
            rows = await self._query_rows(f"SELECT account_role, statement_section, signed_amount FROM {self.summary_view}")
        else:
            where_clause, params = self._build_where(active_filters, as_of=as_of, start_at=start_at, end_at=end_at)
            rows = await self._query_rows(
                f"SELECT account_role, statement_section, signed_amount FROM {self.entries_view} WHERE {where_clause}",
                tuple(params),
            )

        values: dict[str, float] = {
            "cash": 0.0,
            "bank_accounts": 0.0,
            "recoverable_tax": 0.0,
            "inventory": 0.0,
            "accounts_payable": 0.0,
            "short_term_loans": 0.0,
            "tax_payable": 0.0,
            "revenue": 0.0,
            "returns": 0.0,
            "marketplace_fees": 0.0,
            "freight_out": 0.0,
            "bank_fees": 0.0,
            "financial_expenses": 0.0,
            "cmv": 0.0,
            "other_expenses": 0.0,
        }
        for row in rows:
            account_role = str(row.get("account_role") or "")
            statement_section = str(row.get("statement_section") or "")
            signed_amount = float(row.get("signed_amount", 0.0) or 0.0)
            if account_role == "cash":
                values["cash"] += signed_amount
            elif account_role == "bank_accounts":
                values["bank_accounts"] += signed_amount
            elif account_role == "recoverable_tax":
                values["recoverable_tax"] += signed_amount
            elif account_role == "inventory":
                values["inventory"] += signed_amount
            elif account_role == "accounts_payable":
                values["accounts_payable"] += abs(signed_amount)
            elif account_role == "short_term_loans":
                values["short_term_loans"] += abs(signed_amount)
            elif account_role == "tax_payable":
                values["tax_payable"] += abs(signed_amount)
            elif account_role == "revenue":
                values["revenue"] += abs(signed_amount)
            elif account_role == "returns":
                values["returns"] += signed_amount
            elif account_role == "marketplace_fees":
                values["marketplace_fees"] += signed_amount
            elif account_role == "outbound_freight":
                values["freight_out"] += signed_amount
            elif account_role == "bank_fees":
                values["bank_fees"] += signed_amount
            elif account_role == "interest_expense":
                values["financial_expenses"] += signed_amount
            elif account_role == "cogs":
                values["cmv"] += signed_amount
            elif statement_section == "expense":
                values["other_expenses"] += signed_amount

        for key in list(values):
            values[key] = round(values[key], 2)

        metrics = self._income_statement_metrics(
            revenue=values["revenue"],
            returns=values["returns"],
            marketplace_fees=values["marketplace_fees"],
            freight_out=values["freight_out"],
            bank_fees=values["bank_fees"],
            financial_expenses=values["financial_expenses"],
            other_expenses=values["other_expenses"],
            cmv=values["cmv"],
        )
        liabilities_total = round(values["accounts_payable"] + values["short_term_loans"] + values["tax_payable"], 2)
        net_revenue = round(float(metrics["net_revenue"] or 0.0), 2)
        gross_profit = round(float(metrics["gross_profit"] or 0.0), 2)
        operating_expenses = round(float(metrics["operating_expenses"] or 0.0), 2)
        expenses_total = round(float(metrics["expenses"] or 0.0), 2)
        net_income = round(float(metrics["net_income"] or 0.0), 2)
        assets_total = round(values["cash"] + values["bank_accounts"] + values["recoverable_tax"] + values["inventory"], 2)
        equity_total = round(assets_total - liabilities_total, 2)
        liabilities_and_equity = round(liabilities_total + equity_total, 2)
        difference = round(assets_total - liabilities_and_equity, 2)

        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "as_of": cutoff,
            "balance_sheet": {
                "assets": {
                    "cash": values["cash"],
                    "bank_accounts": values["bank_accounts"],
                    "recoverable_tax": values["recoverable_tax"],
                    "inventory": values["inventory"],
                    "total": assets_total,
                },
                "liabilities": {
                    "accounts_payable": values["accounts_payable"],
                    "short_term_loans": values["short_term_loans"],
                    "tax_payable": values["tax_payable"],
                    "total": liabilities_total,
                },
                "equity": {"current_earnings": net_income, "total": equity_total},
                "total_liabilities_and_equity": liabilities_and_equity,
                "difference": difference,
            },
            "income_statement": {
                "revenue": values["revenue"],
                "returns": values["returns"],
                "net_revenue": net_revenue,
                "marketplace_fees": values["marketplace_fees"],
                "freight_out": values["freight_out"],
                "bank_fees": values["bank_fees"],
                "financial_expenses": values["financial_expenses"],
                "other_expenses": values["other_expenses"],
                "operating_expenses": operating_expenses,
                "expenses": expenses_total,
                "net_income": net_income,
                "cmv": values["cmv"],
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
        where_clause, params = self._build_where(filters or {}, as_of=as_of, start_at=start_at, end_at=end_at)
        safe_limit = max(int(limit), 1)
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
        FROM {self.entries_view}
        WHERE {where_clause}
        ORDER BY occurred_at DESC
        LIMIT {safe_limit}
        """.strip()
        rows = await self._query_rows(sql, tuple(params))
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
                    "occurred_at": row.get("occurred_at").astimezone(timezone.utc).isoformat() if isinstance(row.get("occurred_at"), datetime) else None,
                    "ingested_at": row.get("ingested_at").astimezone(timezone.utc).isoformat() if isinstance(row.get("ingested_at"), datetime) else None,
                    "revision": int(row.get("revision", 1) or 1),
                }
            )
        return normalized_rows

    async def get_filter_options(self) -> dict[str, list[str]]:
        query_map = {
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

        async def fetch_distinct(column: str) -> list[str]:
            rows = await self._query_rows(
                f"SELECT DISTINCT {column} AS value FROM {self.entries_view} WHERE {column} IS NOT NULL AND {column} <> '' AND {column} <> 'null' ORDER BY value LIMIT 500"
            )
            return [str(row.get("value")) for row in rows if row.get("value")]

        values = await asyncio.gather(*(fetch_distinct(column) for column in query_map.values()))
        return {key: sorted(set(value)) for key, value in zip(query_map.keys(), values, strict=False)}

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
        safe_limit = max(int(limit), 1)
        rows = await self._query_rows(
            f"SELECT DISTINCT {column} AS value FROM {self.entries_view} WHERE {column} IS NOT NULL AND {column} <> '' AND {column} <> 'null' AND {column} ILIKE %s ORDER BY value LIMIT {safe_limit}",
            (f"%{normalized_query}%",),
        )
        return [str(item.get("value")) for item in rows if item.get("value")]

    async def get_sales_workspace(
        self,
        *,
        as_of: str | None = None,
        start_at: str | None = None,
        end_at: str | None = None,
        filters: dict[str, str | None] | None = None,
    ) -> dict[str, Any]:
        active_filters = filters or {}
        use_sales_view = not any(active_filters.values()) and not start_at and not end_at and not as_of

        if use_sales_view:
            sales_sql = f"SELECT * FROM {self.sales_view} ORDER BY occurred_at DESC LIMIT 40"
            kpi_sql = f"SELECT COUNT(*) AS order_count, COUNT(DISTINCT COALESCE(customer_email, COALESCE(customer_id, sale_id))) AS unique_customers, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales, COALESCE(SUM(quantity), 0) AS units_sold, COALESCE(AVG(cart_items_count), 0) AS avg_items_per_order FROM {self.sales_view}"
            channel_sql = f"SELECT channel_name AS label, COUNT(*) AS order_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.sales_view} GROUP BY channel_name ORDER BY net_sales DESC LIMIT 8"
            product_sql = f"SELECT lead_product AS label, COUNT(*) AS order_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.sales_view} GROUP BY lead_product ORDER BY net_sales DESC LIMIT 8"
            status_sql = f"SELECT order_status AS label, COUNT(*) AS order_count, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.sales_view} WHERE order_status IS NOT NULL AND order_status <> '' GROUP BY order_status ORDER BY order_count DESC LIMIT 6"
            payment_sql = f"SELECT payment_method AS label, COUNT(*) AS order_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.sales_view} WHERE payment_method IS NOT NULL AND payment_method <> '' AND payment_method <> 'null' GROUP BY payment_method ORDER BY net_sales DESC LIMIT 12"
            params: tuple[Any, ...] = ()
        else:
            where_clause, params_list = self._build_where(active_filters, as_of=as_of, start_at=start_at, end_at=end_at)
            sales_where = f"{where_clause} AND ontology_event_type = 'sale' AND account_role = 'revenue' AND sale_id IS NOT NULL AND sale_id <> ''"
            sales_sql = f"SELECT sale_id, MAX(order_id) AS order_id, MAX(occurred_at) AS occurred_at, MAX(customer_id) AS customer_id, MAX(customer_name) AS customer_name, MAX(customer_cpf) AS customer_cpf, MAX(customer_email) AS customer_email, MAX(customer_segment) AS customer_segment, MAX(channel) AS channel, MAX(channel_name) AS channel_name, MAX(payment_method) AS payment_method, MAX(payment_installments) AS payment_installments, MAX(order_status) AS order_status, MAX(order_origin) AS order_origin, MAX(coupon_code) AS coupon_code, MAX(device_type) AS device_type, MAX(sales_region) AS sales_region, MAX(freight_service) AS freight_service, MAX(product_name) AS lead_product, COUNT(DISTINCT product_id) AS product_mix, MAX(cart_items_count) AS cart_items_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_amount, COALESCE(SUM(net_amount), 0) AS net_amount, MAX(cart_discount) AS cart_discount, COALESCE(SUM(tax_amount), 0) AS tax_amount, COALESCE(SUM(marketplace_fee_amount), 0) AS marketplace_fee_amount, COALESCE(SUM(inventory_cost_total), 0) AS cmv FROM {self.entries_view} WHERE {sales_where} GROUP BY sale_id ORDER BY occurred_at DESC LIMIT 40"
            kpi_sql = f"SELECT COUNT(DISTINCT sale_id) AS order_count, COUNT(DISTINCT COALESCE(customer_email, COALESCE(customer_id, sale_id))) AS unique_customers, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales, COALESCE(SUM(quantity), 0) AS units_sold, COALESCE(AVG(cart_items_count), 0) AS avg_items_per_order FROM {self.entries_view} WHERE {sales_where}"
            channel_sql = f"SELECT channel_name AS label, COUNT(DISTINCT sale_id) AS order_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.entries_view} WHERE {sales_where} GROUP BY channel_name ORDER BY net_sales DESC LIMIT 8"
            product_sql = f"SELECT product_name AS label, COUNT(DISTINCT sale_id) AS order_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.entries_view} WHERE {sales_where} GROUP BY product_name ORDER BY net_sales DESC LIMIT 8"
            status_sql = f"SELECT order_status AS label, COUNT(DISTINCT sale_id) AS order_count, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.entries_view} WHERE {sales_where} AND order_status IS NOT NULL AND order_status <> '' GROUP BY order_status ORDER BY order_count DESC LIMIT 6"
            payment_sql = f"SELECT payment_method AS label, COUNT(DISTINCT sale_id) AS order_count, COALESCE(SUM(quantity), 0) AS quantity, COALESCE(SUM(gross_amount), 0) AS gross_sales, COALESCE(SUM(net_amount), 0) AS net_sales FROM {self.entries_view} WHERE {sales_where} AND payment_method IS NOT NULL AND payment_method <> '' AND payment_method <> 'null' GROUP BY payment_method ORDER BY net_sales DESC LIMIT 12"
            params = tuple(params_list)

        try:
            sales, kpis, by_channel, by_product, by_status, by_payment_rows = await asyncio.gather(
                self._query_rows(sales_sql, params),
                self._query_row(kpi_sql, params),
                self._query_rows(channel_sql, params),
                self._query_rows(product_sql, params),
                self._query_rows(status_sql, params),
                self._query_rows(payment_sql, params),
            )
        except MaterializeQueryError:
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

        normalized_sales = []
        for sale in sales:
            normalized_sales.append(
                {
                    **sale,
                    "occurred_at": sale.get("occurred_at").astimezone(timezone.utc).isoformat() if isinstance(sale.get("occurred_at"), datetime) else None,
                    "quantity": round(float(sale.get("quantity", 0.0) or 0.0), 3),
                    "gross_amount": round(float(sale.get("gross_amount", 0.0) or 0.0), 2),
                    "net_amount": round(float(sale.get("net_amount", 0.0) or 0.0), 2),
                    "cart_discount": round(float(sale.get("cart_discount", 0.0) or 0.0), 2),
                    "tax_amount": round(float(sale.get("tax_amount", 0.0) or 0.0), 2),
                    "marketplace_fee_amount": round(float(sale.get("marketplace_fee_amount", 0.0) or 0.0), 2),
                    "cmv": round(float(sale.get("cmv", 0.0) or 0.0), 2),
                    "product_mix": int(sale.get("product_mix", 0) or 0),
                    "cart_items_count": int(sale.get("cart_items_count", 0) or 0),
                    "payment_installments": int(sale.get("payment_installments", 0) or 0),
                }
            )

        order_count = int(kpis.get("order_count", 0) or 0)
        net_sales = round(float(kpis.get("net_sales", 0.0) or 0.0), 2)
        by_payment = self._normalize_breakdown_rows(by_payment_rows)[:8]
        return {
            "sales": normalized_sales,
            "kpis": {
                "order_count": order_count,
                "unique_customers": int(kpis.get("unique_customers", 0) or 0),
                "gross_sales": round(float(kpis.get("gross_sales", 0.0) or 0.0), 2),
                "net_sales": net_sales,
                "units_sold": round(float(kpis.get("units_sold", 0.0) or 0.0), 3),
                "average_ticket": round(net_sales / order_count, 2) if order_count else 0.0,
                "avg_items_per_order": round(float(kpis.get("avg_items_per_order", 0.0) or 0.0), 2),
                "gross_margin": 0.0,
            },
            "by_channel": self._normalize_breakdown_rows(by_channel),
            "by_product": self._normalize_breakdown_rows(by_product),
            "by_status": [{"label": str(row.get("label") or "nao_informado"), "order_count": int(row.get("order_count", 0) or 0), "net_sales": round(float(row.get("net_sales", 0.0) or 0.0), 2)} for row in by_status],
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
            self._query_rows(f"SELECT account_code, current_balance, entry_count FROM {self.account_balances_view} ORDER BY account_code LIMIT 500"),
        )
        balances_by_code = {item["account_code"]: item for item in balances}
        rows = []
        for account in accounts:
            balance = balances_by_code.get(account["account_code"], {})
            rows.append(
                {
                    **account,
                    "current_balance": round(float(balance.get("current_balance", 0.0) or 0.0), 2),
                    "entry_count": int(balance.get("entry_count", 0) or 0),
                }
            )
        return rows

    async def get_product_catalog(self) -> list[dict[str, Any]]:
        products, channels, aggregates = await asyncio.gather(
            self._fetch_json("/api/v1/master-data/products", []),
            self._fetch_json("/api/v1/master-data/channels", []),
            self._query_rows(f"SELECT * FROM {self.product_metrics_view} ORDER BY product_id LIMIT 2000"),
        )
        channel_map = {item.get("channel_id"): item.get("channel_name") for item in channels if isinstance(item, dict)}
        aggregates_by_product = {item["product_id"]: item for item in aggregates}
        rows = []
        for product in products:
            aggregate = aggregates_by_product.get(product["product_id"], {})
            average_purchase_price = round(float(aggregate.get("average_purchase_price", 0.0) or 0.0), 2) or round(float(product.get("base_cost", 0.0)), 2)
            average_sale_price = round(float(aggregate.get("average_sale_price", 0.0) or 0.0), 2) or round(float(product.get("base_price", 0.0)), 2)
            opening_stock_quantity = round(sum(float(value) for value in (product.get("initial_stock") or {}).values()), 3)
            stock_delta_quantity = float(aggregate.get("stock_delta_quantity", 0.0) or 0.0)
            stock_quantity = round(max(opening_stock_quantity + stock_delta_quantity, 0.0), 3)
            sold_quantity = round(float(aggregate.get("sold_quantity", 0.0) or 0.0), 3)
            returned_quantity = round(float(aggregate.get("returned_quantity", 0.0) or 0.0), 3)
            net_sold_quantity = round(max(sold_quantity - returned_quantity, 0.0), 3)
            revenue_amount = round(float(aggregate.get("revenue_amount", 0.0) or 0.0), 2)
            return_amount = round(float(aggregate.get("return_amount", 0.0) or 0.0), 2)
            net_revenue_amount = round(revenue_amount - return_amount, 2)
            cogs_amount = round(float(aggregate.get("cogs_amount", 0.0) or 0.0), 2)
            marketplace_fees_amount = round(float(aggregate.get("marketplace_fees_amount", 0.0) or 0.0), 2)
            freight_out_amount = round(float(aggregate.get("freight_out_amount", 0.0) or 0.0), 2)
            bank_fees_amount = round(float(aggregate.get("bank_fees_amount", 0.0) or 0.0), 2)
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