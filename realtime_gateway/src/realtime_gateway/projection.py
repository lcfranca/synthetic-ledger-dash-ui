from __future__ import annotations

from typing import Any


def round_value(value: float, digits: int = 2) -> float:
    factor = 10**digits
    return round(float(value) * factor) / factor


def percentage(numerator: float, denominator: float, digits: int = 2) -> float | None:
    if abs(float(denominator)) < 0.0001:
        return None
    return round_value((float(numerator) / float(denominator)) * 100.0, digits)


def income_statement_metrics(values: dict[str, float]) -> dict[str, float | None]:
    net_revenue = round_value(values["revenue"] - values["returns"])
    gross_profit = round_value(net_revenue - values["cmv"])
    operating_expenses = round_value(
        values["marketplace_fees"] + values["freight_out"] + values["bank_fees"] + values["other_expenses"]
    )
    expenses = round_value(operating_expenses + values["financial_expenses"] + values["cmv"])
    net_income = round_value(net_revenue - expenses)
    return {
        "net_revenue": net_revenue,
        "gross_profit": gross_profit,
        "operating_expenses": operating_expenses,
        "expenses": expenses,
        "net_income": net_income,
        "return_rate_pct": percentage(values["returns"], values["revenue"]),
        "gross_margin_pct": percentage(gross_profit, net_revenue),
        "net_margin_pct": percentage(net_income, net_revenue),
        "expense_ratio_pct": percentage(operating_expenses, net_revenue),
    }


def enrich_product_metrics(product: dict[str, Any]) -> dict[str, Any]:
    revenue_amount = round_value(product.get("revenue_amount", 0.0))
    return_amount = round_value(product.get("return_amount", 0.0))
    net_revenue_amount = round_value(product.get("net_revenue_amount", revenue_amount - return_amount))
    cogs_amount = round_value(product.get("cogs_amount", 0.0))
    selling_expenses_amount = round_value(product.get("selling_expenses_amount", 0.0))
    gross_profit_amount = round_value(product.get("gross_profit_amount", net_revenue_amount - cogs_amount))
    net_profit_amount = round_value(product.get("net_profit_amount", gross_profit_amount - selling_expenses_amount))
    net_sold_quantity = round_value(
        max(float(product.get("net_sold_quantity", float(product.get("sold_quantity", 0.0)) - float(product.get("returned_quantity", 0.0)))), 0.0),
        3,
    )
    return {
        **product,
        "net_sold_quantity": net_sold_quantity,
        "revenue_amount": revenue_amount,
        "return_amount": return_amount,
        "net_revenue_amount": net_revenue_amount,
        "cogs_amount": cogs_amount,
        "selling_expenses_amount": selling_expenses_amount,
        "gross_profit_amount": gross_profit_amount,
        "net_profit_amount": net_profit_amount,
        "return_rate_pct": percentage(float(product.get("returned_quantity", 0.0)), float(product.get("sold_quantity", 0.0)), 2),
        "gross_margin_pct": percentage(gross_profit_amount, net_revenue_amount, 2),
        "net_margin_pct": percentage(net_profit_amount, net_revenue_amount, 2),
    }


def supply_plan_for_product(product: dict[str, Any]) -> dict[str, Any]:
    effective_stock = max(round_value(float(product.get("current_stock_quantity", 0.0)), 3), 0.0)
    demand_weight = max(float(product.get("demand_weight", 0.0) or 0.0), 0.1)
    daily_demand_units = round_value(max(float(product.get("net_sold_quantity", 0.0)) / 30.0, demand_weight), 3)
    coverage_days = round_value(effective_stock / daily_demand_units, 1) if daily_demand_units > 0 else None
    reorder_point = float(product.get("reorder_point", 0.0) or 0.0)
    target_stock = float(product.get("target_stock", 0.0) or 0.0)
    suggested_purchase_quantity = round_value(max(target_stock - effective_stock, 0.0), 3)
    suggested_supplier_name = str(product.get("supplier_name") or product.get("preferred_supplier_id") or "Fornecedor padrao")
    needs_restock = effective_stock <= reorder_point
    purchase_recommendation = (
        f"Comprar {suggested_purchase_quantity:g} un de {suggested_supplier_name}"
        if needs_restock and suggested_purchase_quantity > 0
        else f"Sem compra sugerida para {suggested_supplier_name}"
    )
    return {
        "daily_demand_units": daily_demand_units,
        "coverage_days": coverage_days,
        "suggested_purchase_quantity": suggested_purchase_quantity,
        "suggested_purchase_supplier_name": suggested_supplier_name,
        "purchase_recommendation": purchase_recommendation,
        "needs_restock": needs_restock,
    }


def seed_runtime_metadata(workspace: dict[str, Any]) -> dict[str, Any]:
    customer_keys: dict[str, bool] = {}
    sale_products: dict[str, dict[str, bool]] = {}
    for sale in workspace.get("sales_workspace", {}).get("sales", []):
        sale_key = sale.get("sale_id") or sale.get("order_id")
        if not sale_key:
            continue
        customer_key = sale.get("customer_email") or sale.get("customer_id") or sale_key
        customer_keys[str(customer_key)] = True
        sale_products[str(sale_key)] = {str(sale.get("lead_product") or "unknown-product"): True}
    return {"customerKeys": customer_keys, "saleProducts": sale_products}


def create_empty_breakdown(label: str) -> dict[str, Any]:
    return {"label": label, "order_count": 0, "quantity": 0.0, "gross_sales": 0.0, "net_sales": 0.0}


def update_breakdown(
    rows: list[dict[str, Any]],
    label: str,
    delta: dict[str, float | int],
    sort_key: str,
) -> list[dict[str, Any]]:
    if not label:
        return rows
    index = next((i for i, row in enumerate(rows) if row.get("label") == label), -1)
    current = rows[index] if index >= 0 else create_empty_breakdown(label)
    next_row = {
        **current,
        "order_count": int(current.get("order_count", 0)) + int(delta.get("orderCount", 0) or 0),
        "quantity": round_value(float(current.get("quantity", 0.0)) + float(delta.get("quantity", 0.0) or 0.0), 3),
        "gross_sales": round_value(float(current.get("gross_sales", 0.0)) + float(delta.get("grossSales", 0.0) or 0.0)),
        "net_sales": round_value(float(current.get("net_sales", 0.0)) + float(delta.get("netSales", 0.0) or 0.0)),
    }
    next_rows = list(rows)
    if index >= 0:
        next_rows[index] = next_row
    else:
        next_rows.append(next_row)
    next_rows.sort(key=lambda row: float(row.get(sort_key, 0.0) or 0.0), reverse=True)
    return next_rows[:8]


def update_summary(summary: dict[str, Any], entry: dict[str, Any], backend: str, ts: str, next_entries: list[dict[str, Any]]) -> dict[str, Any]:
    balance_sheet = summary.get("balance_sheet", {})
    assets = balance_sheet.get("assets", {})
    liabilities = balance_sheet.get("liabilities", {})
    income_statement = summary.get("income_statement", {})

    cash = float(assets.get("cash", 0.0))
    bank_accounts = float(assets.get("bank_accounts", 0.0))
    recoverable_tax = float(assets.get("recoverable_tax", 0.0))
    inventory = float(assets.get("inventory", 0.0))
    accounts_payable_raw = -float(liabilities.get("accounts_payable", 0.0))
    short_term_loans_raw = -float(liabilities.get("short_term_loans", 0.0))
    tax_payable_raw = -float(liabilities.get("tax_payable", 0.0))
    revenue_raw = -float(income_statement.get("revenue", 0.0))
    returns_raw = float(income_statement.get("returns", 0.0))
    marketplace_fees_raw = float(income_statement.get("marketplace_fees", 0.0))
    freight_out_raw = float(income_statement.get("freight_out", 0.0))
    bank_fees_raw = float(income_statement.get("bank_fees", 0.0))
    financial_expenses_raw = float(income_statement.get("financial_expenses", 0.0))
    other_expenses_raw = float(income_statement.get("other_expenses", 0.0))
    cmv_raw = float(income_statement.get("cmv", 0.0))

    account_role = str(entry.get("account_role") or "")
    signed_amount = float(entry.get("signed_amount", 0.0) or 0.0)
    entry_category = str(entry.get("entry_category") or "")

    if account_role == "cash":
        cash = round_value(cash + signed_amount)
    elif account_role == "bank_accounts":
        bank_accounts = round_value(bank_accounts + signed_amount)
    elif account_role == "recoverable_tax":
        recoverable_tax = round_value(recoverable_tax + signed_amount)
    elif account_role == "inventory":
        inventory = round_value(inventory + signed_amount)
    elif account_role == "accounts_payable":
        accounts_payable_raw = round_value(accounts_payable_raw + signed_amount)
    elif account_role == "short_term_loans":
        short_term_loans_raw = round_value(short_term_loans_raw + signed_amount)
    elif account_role == "tax_payable":
        tax_payable_raw = round_value(tax_payable_raw + signed_amount)
    elif account_role == "revenue":
        revenue_raw = round_value(revenue_raw + signed_amount)
    elif account_role == "returns":
        returns_raw = round_value(returns_raw + signed_amount)
    elif account_role == "marketplace_fees":
        marketplace_fees_raw = round_value(marketplace_fees_raw + signed_amount)
    elif account_role == "outbound_freight":
        freight_out_raw = round_value(freight_out_raw + signed_amount)
    elif account_role == "bank_fees":
        bank_fees_raw = round_value(bank_fees_raw + signed_amount)
    elif account_role == "interest_expense":
        financial_expenses_raw = round_value(financial_expenses_raw + signed_amount)
    elif account_role == "cogs":
        cmv_raw = round_value(cmv_raw + signed_amount)
    elif entry_category == "despesa" or account_role.endswith("_expense"):
        other_expenses_raw = round_value(other_expenses_raw + signed_amount)

    accounts_payable = round_value(abs(accounts_payable_raw))
    short_term_loans = round_value(abs(short_term_loans_raw))
    tax_payable = round_value(abs(tax_payable_raw))
    revenue = round_value(abs(revenue_raw))
    returns = round_value(returns_raw)
    marketplace_fees = round_value(marketplace_fees_raw)
    freight_out = round_value(freight_out_raw)
    bank_fees = round_value(bank_fees_raw)
    financial_expenses = round_value(financial_expenses_raw)
    other_expenses = round_value(other_expenses_raw)
    cmv = round_value(cmv_raw)

    metrics = income_statement_metrics(
        {
            "revenue": revenue,
            "returns": returns,
            "marketplace_fees": marketplace_fees,
            "freight_out": freight_out,
            "bank_fees": bank_fees,
            "financial_expenses": financial_expenses,
            "other_expenses": other_expenses,
            "cmv": cmv,
        }
    )

    liabilities_total = round_value(accounts_payable + short_term_loans + tax_payable)
    net_revenue = float(metrics["net_revenue"] or 0.0)
    gross_profit = float(metrics["gross_profit"] or 0.0)
    operating_expenses = float(metrics["operating_expenses"] or 0.0)
    expenses = float(metrics["expenses"] or 0.0)
    net_income = float(metrics["net_income"] or 0.0)
    assets_total = round_value(cash + bank_accounts + recoverable_tax + inventory)
    equity_total = round_value(assets_total - liabilities_total)
    total_liabilities_and_equity = round_value(liabilities_total + equity_total)
    difference = round_value(assets_total - total_liabilities_and_equity)

    return {
        **summary,
        "backend": backend,
        "timestamp": ts,
        "entries": next_entries,
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
            "total_liabilities_and_equity": total_liabilities_and_equity,
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
            "expenses": expenses,
            "net_income": net_income,
            "cmv": cmv,
            "gross_profit": gross_profit,
            "return_rate_pct": metrics["return_rate_pct"],
            "gross_margin_pct": metrics["gross_margin_pct"],
            "net_margin_pct": metrics["net_margin_pct"],
            "expense_ratio_pct": metrics["expense_ratio_pct"],
        },
    }


def update_accounts(accounts: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    account_code = entry.get("account_code")
    index = next((i for i, account in enumerate(accounts) if account.get("account_code") == account_code), -1)
    if index < 0:
        return accounts
    next_accounts = list(accounts)
    current = dict(next_accounts[index])
    current["current_balance"] = round_value(float(current.get("current_balance", 0.0)) + float(entry.get("signed_amount", 0.0) or 0.0))
    current["entry_count"] = int(current.get("entry_count", 0)) + 1
    next_accounts[index] = current
    return next_accounts


def update_products(products: list[dict[str, Any]], entry: dict[str, Any]) -> list[dict[str, Any]]:
    product_id = entry.get("product_id")
    if not product_id:
        return products
    index = next((i for i, product in enumerate(products) if product.get("product_id") == product_id), -1)
    if index < 0:
        return products
    current = dict(products[index])
    current_stock_quantity = float(current.get("current_stock_quantity", 0.0))
    sold_quantity = float(current.get("sold_quantity", 0.0))
    net_sold_quantity = float(current.get("net_sold_quantity", 0.0))
    returned_quantity = float(current.get("returned_quantity", 0.0))
    average_purchase_price = float(current.get("average_purchase_price", 0.0))

    if entry.get("account_role") == "inventory":
        quantity = float(entry.get("quantity", 0.0) or 0.0)
        stock_delta = quantity if entry.get("entry_side") == "debit" else -quantity
        current_stock_quantity = round_value(current_stock_quantity + stock_delta, 3)
        if entry.get("ontology_event_type") == "return":
            returned_quantity = round_value(returned_quantity + quantity, 3)
            net_sold_quantity = round_value(max(net_sold_quantity - quantity, 0.0), 3)
        elif entry.get("ontology_event_type") == "sale":
            sold_quantity = round_value(sold_quantity + quantity, 3)
            net_sold_quantity = round_value(net_sold_quantity + quantity, 3)
        elif entry.get("ontology_event_type") == "purchase":
            average_purchase_price = round_value((average_purchase_price + float(entry.get("unit_price", 0.0) or 0.0)) / 2.0, 2)

    next_product = enrich_product_metrics(
        {
            **current,
            "current_stock_quantity": current_stock_quantity,
            "sold_quantity": sold_quantity,
            "net_sold_quantity": net_sold_quantity,
            "returned_quantity": returned_quantity,
            "average_purchase_price": average_purchase_price,
        }
    )
    next_product = {**next_product, **supply_plan_for_product(next_product)}
    next_products = list(products)
    next_products[index] = next_product
    return next_products


def update_sales_workspace(sales_workspace: dict[str, Any], entry: dict[str, Any], runtime: dict[str, Any]) -> dict[str, Any]:
    if entry.get("ontology_event_type") != "sale":
        return sales_workspace
    sale_key = entry.get("sale_id") or entry.get("order_id")
    if not sale_key:
        return sales_workspace

    sales = list(sales_workspace.get("sales", []))
    sale_index = next((i for i, sale in enumerate(sales) if sale.get("sale_id") == sale_key or sale.get("order_id") == entry.get("order_id")), -1)
    existing_sale = dict(sales[sale_index]) if sale_index >= 0 else None
    product_key = str(entry.get("product_name") or entry.get("product_id") or "unknown-product")
    customer_key = str(entry.get("customer_email") or entry.get("customer_id") or sale_key)
    sale_products = dict(runtime.get("saleProducts", {}).get(str(sale_key), {}))
    is_new_sale = existing_sale is None
    is_new_product = not sale_products.get(product_key)
    sale_products[product_key] = True
    runtime.setdefault("saleProducts", {})[str(sale_key)] = sale_products

    next_sale = {
        "sale_id": existing_sale.get("sale_id") if existing_sale else sale_key,
        "order_id": existing_sale.get("order_id") if existing_sale else entry.get("order_id"),
        "occurred_at": max(str(existing_sale.get("occurred_at") if existing_sale else ""), str(entry.get("occurred_at") or "")),
        "customer_id": (existing_sale or {}).get("customer_id") or entry.get("customer_id"),
        "customer_name": (existing_sale or {}).get("customer_name") or entry.get("customer_name"),
        "customer_cpf": (existing_sale or {}).get("customer_cpf") or entry.get("customer_cpf"),
        "customer_email": (existing_sale or {}).get("customer_email") or entry.get("customer_email"),
        "customer_segment": (existing_sale or {}).get("customer_segment") or entry.get("customer_segment"),
        "channel": (existing_sale or {}).get("channel") or entry.get("channel"),
        "channel_name": (existing_sale or {}).get("channel_name") or entry.get("channel_name"),
        "payment_method": (existing_sale or {}).get("payment_method") or entry.get("payment_method"),
        "payment_installments": max(int((existing_sale or {}).get("payment_installments", 0) or 0), int(entry.get("payment_installments", 0) or 0)),
        "order_status": (existing_sale or {}).get("order_status") or entry.get("order_status"),
        "order_origin": (existing_sale or {}).get("order_origin") or entry.get("order_origin"),
        "coupon_code": (existing_sale or {}).get("coupon_code") or entry.get("coupon_code"),
        "device_type": (existing_sale or {}).get("device_type") or entry.get("device_type"),
        "sales_region": (existing_sale or {}).get("sales_region") or entry.get("sales_region"),
        "freight_service": (existing_sale or {}).get("freight_service") or entry.get("freight_service"),
        "lead_product": (existing_sale or {}).get("lead_product") or entry.get("product_name") or entry.get("product_id"),
        "product_mix": 1 if is_new_sale else int(existing_sale.get("product_mix", 0)) + (1 if is_new_product else 0),
        "cart_items_count": max(int((existing_sale or {}).get("cart_items_count", 0) or 0), int(entry.get("cart_items_count", 0) or 0)),
        "quantity": float((existing_sale or {}).get("quantity", 0.0) or 0.0),
        "gross_amount": float((existing_sale or {}).get("gross_amount", 0.0) or 0.0),
        "net_amount": float((existing_sale or {}).get("net_amount", 0.0) or 0.0),
        "cart_discount": max(float((existing_sale or {}).get("cart_discount", 0.0) or 0.0), float(entry.get("cart_discount", 0.0) or 0.0)),
        "tax_amount": float((existing_sale or {}).get("tax_amount", 0.0) or 0.0),
        "marketplace_fee_amount": float((existing_sale or {}).get("marketplace_fee_amount", 0.0) or 0.0),
        "cmv": float((existing_sale or {}).get("cmv", 0.0) or 0.0),
    }

    gross_sales_delta = 0.0
    net_sales_delta = 0.0
    gross_margin_delta = 0.0
    units_sold_delta = 0.0
    account_role = entry.get("account_role")
    quantity = float(entry.get("quantity", 0.0) or 0.0)
    amount = float(entry.get("amount", 0.0) or 0.0)
    unit_price = float(entry.get("unit_price", 0.0) or 0.0)

    if account_role == "revenue":
        gross_sales_delta = round_value(unit_price * quantity)
        net_sales_delta = round_value(amount)
        gross_margin_delta = round_value(gross_margin_delta + net_sales_delta)
        units_sold_delta = round_value(quantity, 3)
        next_sale["quantity"] = round_value(float(next_sale["quantity"]) + quantity, 3)
        next_sale["gross_amount"] = round_value(float(next_sale["gross_amount"]) + gross_sales_delta)
        next_sale["net_amount"] = round_value(float(next_sale["net_amount"]) + net_sales_delta)
    elif account_role == "marketplace_fees":
        next_sale["marketplace_fee_amount"] = round_value(float(next_sale["marketplace_fee_amount"]) + amount)
    elif account_role == "tax_payable":
        next_sale["tax_amount"] = round_value(float(next_sale["tax_amount"]) + amount)
    elif account_role == "cogs":
        next_sale["cmv"] = round_value(float(next_sale["cmv"]) + amount)
        gross_margin_delta = round_value(gross_margin_delta - amount)

    if is_new_sale:
        sales.insert(0, next_sale)
    else:
        sales[sale_index] = next_sale
    sales.sort(key=lambda sale: str(sale.get("occurred_at") or ""), reverse=True)

    kpis = sales_workspace.get("kpis", {})
    next_order_count = int(kpis.get("order_count", 0) or 0) + (1 if is_new_sale and account_role == "revenue" else 0)
    next_unique_customers = int(kpis.get("unique_customers", 0) or 0)
    if is_new_sale and account_role == "revenue" and not runtime.setdefault("customerKeys", {}).get(customer_key):
        runtime["customerKeys"][customer_key] = True
        next_unique_customers += 1

    next_gross_sales = round_value(float(kpis.get("gross_sales", 0.0) or 0.0) + gross_sales_delta)
    next_net_sales = round_value(float(kpis.get("net_sales", 0.0) or 0.0) + net_sales_delta)
    next_gross_margin = round_value(float(kpis.get("gross_margin", 0.0) or 0.0) + gross_margin_delta)
    next_units_sold = round_value(float(kpis.get("units_sold", 0.0) or 0.0) + units_sold_delta, 3)
    next_average_ticket = round_value(next_net_sales / next_order_count) if next_order_count > 0 else 0.0
    next_avg_items_per_order = (
        round_value(((float(kpis.get("avg_items_per_order", 0.0) or 0.0) * max(next_order_count - 1, 0)) + float(entry.get("cart_items_count", 0) or 0.0)) / next_order_count, 2)
        if is_new_sale and account_role == "revenue" and next_order_count > 0
        else float(kpis.get("avg_items_per_order", 0.0) or 0.0)
    )

    order_delta = 1 if is_new_sale and account_role == "revenue" else 0
    next_by_channel = (
        update_breakdown(
            sales_workspace.get("by_channel", []),
            str(entry.get("channel_name") or entry.get("channel") or ""),
            {"orderCount": order_delta, "quantity": units_sold_delta, "grossSales": gross_sales_delta, "netSales": net_sales_delta},
            "net_sales",
        )
        if account_role == "revenue"
        else sales_workspace.get("by_channel", [])
    )
    next_by_product = (
        update_breakdown(
            sales_workspace.get("by_product", []),
            str(entry.get("product_name") or entry.get("product_id") or ""),
            {"orderCount": 1 if is_new_product else 0, "quantity": units_sold_delta, "grossSales": gross_sales_delta, "netSales": net_sales_delta},
            "net_sales",
        )
        if account_role == "revenue"
        else sales_workspace.get("by_product", [])
    )
    next_by_status = (
        update_breakdown(
            sales_workspace.get("by_status", []),
            str(entry.get("order_status") or ""),
            {"orderCount": order_delta, "netSales": net_sales_delta},
            "order_count",
        )
        if account_role == "revenue" and entry.get("order_status")
        else sales_workspace.get("by_status", [])
    )
    next_by_payment = (
        update_breakdown(
            sales_workspace.get("by_payment", []),
            str(entry.get("payment_method") or "nao_informado"),
            {"orderCount": order_delta, "quantity": units_sold_delta, "grossSales": gross_sales_delta, "netSales": net_sales_delta},
            "net_sales",
        )
        if account_role == "revenue"
        else sales_workspace.get("by_payment", [])
    )

    return {
        **sales_workspace,
        "sales": sales[:40],
        "kpis": {
            "order_count": next_order_count,
            "unique_customers": next_unique_customers,
            "gross_sales": next_gross_sales,
            "net_sales": next_net_sales,
            "gross_margin": next_gross_margin,
            "units_sold": next_units_sold,
            "average_ticket": next_average_ticket,
            "avg_items_per_order": next_avg_items_per_order,
        },
        "by_channel": next_by_channel,
        "by_product": next_by_product,
        "by_status": next_by_status,
        "by_payment": next_by_payment,
    }


def with_realtime_entry(workspace: dict[str, Any] | None, entry: dict[str, Any], backend: str, ts: str, runtime: dict[str, Any] | None = None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not workspace:
        return None, runtime

    runtime_state = runtime or seed_runtime_metadata(workspace)
    current_entries = workspace.get("entries", [])
    next_entries = [entry, *[item for item in current_entries if item.get("entry_id") != entry.get("entry_id")]][:180]
    next_summary = update_summary(workspace.get("summary", {}), entry, backend, ts, next_entries)
    next_accounts = update_accounts(workspace.get("account_catalog", []), entry)
    next_products = update_products(workspace.get("product_catalog", []), entry)
    next_sales_workspace = update_sales_workspace(workspace.get("sales_workspace", {}), entry, runtime_state)

    return (
        {
            **workspace,
            "backend": backend,
            "timestamp": ts,
            "entries": next_entries,
            "summary": next_summary,
            "account_catalog": next_accounts,
            "product_catalog": next_products,
            "sales_workspace": next_sales_workspace,
        },
        runtime_state,
    )