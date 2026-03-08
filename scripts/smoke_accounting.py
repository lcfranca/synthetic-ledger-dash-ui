#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
PRODUCER_SRC = ROOT / "producer" / "src"
if str(PRODUCER_SRC) not in sys.path:
    sys.path.insert(0, str(PRODUCER_SRC))

from producer.domain import Catalog, RetailSimulation


EXPECTED_ACCOUNT_ROLES = {
    "cash",
    "bank_accounts",
    "recoverable_tax",
    "inventory",
    "accounts_payable",
    "short_term_loans",
    "tax_payable",
    "revenue",
    "returns",
    "cogs",
    "marketplace_fees",
    "outbound_freight",
    "bank_fees",
    "interest_expense",
}


def fetch_json(url: str) -> dict | list:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=5) as response:
        return json.loads(response.read().decode("utf-8"))


def wait_for_json(url: str, predicate, timeout_seconds: int, label: str) -> dict | list:
    deadline = time.time() + timeout_seconds
    last_error = "unknown error"
    while time.time() < deadline:
        try:
            payload = fetch_json(url)
            if predicate(payload):
                print(f"[ok] {label}")
                return payload
            last_error = f"predicate not satisfied for {label}"
        except Exception as exc:
            last_error = str(exc)
        time.sleep(2)
    raise RuntimeError(f"timeout waiting for {label}: {last_error}")


def approx_equal(left: float, right: float, tolerance: float = 0.11) -> bool:
    return math.isclose(left, right, abs_tol=tolerance)


def validate_summary(summary: dict, label: str) -> None:
    balance_sheet = summary["balance_sheet"]
    income_statement = summary["income_statement"]

    assets_total = float(balance_sheet["assets"]["total"])
    liabilities_and_equity = float(balance_sheet["total_liabilities_and_equity"])
    difference = float(balance_sheet["difference"])
    net_revenue = float(income_statement["net_revenue"])
    revenue = float(income_statement["revenue"])
    returns = float(income_statement["returns"])
    financial_expenses = float(income_statement.get("financial_expenses", 0.0))
    expenses = float(income_statement["expenses"])
    net_income = float(income_statement["net_income"])
    cash = float(balance_sheet["assets"]["cash"])
    bank_accounts = float(balance_sheet["assets"]["bank_accounts"])

    if not approx_equal(net_revenue, revenue - returns):
        raise RuntimeError(f"{label}: net_revenue != revenue - returns")
    if not approx_equal(net_income, net_revenue - expenses):
        raise RuntimeError(f"{label}: net_income != net_revenue - expenses")
    if not approx_equal(assets_total, liabilities_and_equity) or not approx_equal(difference, 0.0):
        raise RuntimeError(f"{label}: assets total does not match liabilities plus equity")
    if cash < -0.11 or bank_accounts < -0.11:
        raise RuntimeError(f"{label}: treasury assets went negative in summary")
    if financial_expenses < -0.11:
        raise RuntimeError(f"{label}: financial expenses cannot be negative")


def apply_treasury_event(balances: dict[str, float], simulation: RetailSimulation, event: dict) -> None:
    event_type = str(event["event_type"])
    if event_type == "sale":
        amount = round(float(event["net_amount"]) + float(event["tax"]) - float(event["marketplace_fee"]), 2)
        if event["debit_account"] == simulation.account_code("cash"):
            balances["cash"] += amount
        elif event["debit_account"] == simulation.account_code("bank_accounts"):
            balances["bank_accounts"] += amount
        return

    if event_type in {"supplier_payment", "working_capital_repayment", "working_capital_interest_payment"}:
        amount = round(float(event["net_amount"]), 2)
    elif event_type == "return":
        amount = round(float(event["net_amount"]) + float(event["tax"]), 2)
    elif event_type == "freight":
        amount = round(float(event["net_amount"]) + float(event["marketplace_fee"]), 2)
    else:
        amount = 0.0

    if event_type in {"supplier_payment", "return", "freight", "working_capital_repayment", "working_capital_interest_payment"}:
        if event["credit_account"] == simulation.account_code("cash"):
            balances["cash"] -= amount
        elif event["credit_account"] == simulation.account_code("bank_accounts"):
            balances["bank_accounts"] -= amount
        return

    if event_type == "treasury_transfer":
        balances["cash"] -= float(event["net_amount"])
        balances["bank_accounts"] += float(event["net_amount"])
        return

    if event_type == "working_capital_loan":
        balances["bank_accounts"] += float(event["net_amount"])


def validate_treasury_simulation() -> None:
    catalog = Catalog()
    simulation = RetailSimulation(catalog, seed=17)
    simulation.drain_bootstrap_events()
    balances = {"cash": 0.0, "bank_accounts": 0.0}
    funding_events = 0
    interest_events = 0

    for tick in range(3000):
        event = simulation.next_event()
        apply_treasury_event(balances, simulation, event)
        if event["event_type"] == "working_capital_loan":
            funding_events += 1
        if event["event_type"] == "working_capital_interest_payment":
            interest_events += 1
        if balances["cash"] < -0.11 or balances["bank_accounts"] < -0.11:
            raise RuntimeError(
                f"treasury simulation went negative at tick {tick + 1}: "
                f"event={event['event_type']} cash={balances['cash']:.2f} bank={balances['bank_accounts']:.2f}"
            )

    if funding_events <= 0:
        raise RuntimeError("treasury simulation never emitted a working capital funding event")
    if interest_events <= 0:
        raise RuntimeError("treasury simulation never emitted a working capital interest payment event")
    print("[ok] treasury simulation preserved non-negative cash and bank balances")


def validate_backend_summary(url: str, timeout_seconds: int, label: str) -> None:
    summary = wait_for_json(
        url,
        lambda payload: isinstance(payload, dict) and bool(payload.get("entries")),
        timeout_seconds,
        label,
    )
    validate_summary(summary, label)
    print(f"[ok] {label} arithmetic validated")


def validate_storage_writer(timeout_seconds: int) -> None:
    wait_for_json(
        "http://localhost:8092/health",
        lambda payload: isinstance(payload, dict) and payload.get("status") == "ok",
        timeout_seconds,
        "storage writer health",
    )


def main() -> int:
    active_stacks = [item.strip() for item in os.getenv("ACTIVE_STACKS", "pinot").split(",") if item.strip()]
    run_producer_on_start = os.getenv("RUN_PRODUCER_ON_START", "false").lower() == "true"
    timeout_seconds = int(os.getenv("SMOKE_STARTUP_TIMEOUT_SECONDS", "120"))

    wait_for_json(
        "http://localhost:8091/health",
        lambda payload: isinstance(payload, dict) and payload.get("status") == "ok",
        timeout_seconds,
        "master-data health",
    )
    validate_storage_writer(timeout_seconds)

    validate_treasury_simulation()

    if "pinot" in active_stacks:
        wait_for_json(
            "http://localhost:8082/health",
            lambda payload: isinstance(payload, dict) and payload.get("status") == "ok",
            timeout_seconds,
            "api pinot health",
        )

        overview = wait_for_json(
            "http://localhost:8082/api/v1/master-data/overview",
            lambda payload: isinstance(payload, dict) and bool(payload.get("products")) and bool(payload.get("accounts")),
            timeout_seconds,
            "pinot master data overview",
        )

        account_roles = {item.get("account_role") for item in overview.get("accounts", []) if isinstance(item, dict)}
        missing_roles = sorted(EXPECTED_ACCOUNT_ROLES - account_roles)
        if missing_roles:
            raise RuntimeError(f"chart of accounts missing roles: {', '.join(missing_roles)}")
        print("[ok] chart of accounts includes banking, freight and returns roles")

        if run_producer_on_start:
            validate_backend_summary(
                "http://localhost:8082/api/v1/dashboard/summary",
                timeout_seconds,
                "pinot accounting summary",
            )
        else:
            print("[skip] producer auto-start disabled; accounting arithmetic check skipped")

    if "clickhouse" in active_stacks:
        wait_for_json(
            "http://localhost:8080/health",
            lambda payload: isinstance(payload, dict) and payload.get("status") == "ok",
            timeout_seconds,
            "api clickhouse health",
        )
        if run_producer_on_start:
            validate_backend_summary(
                "http://localhost:8080/api/v1/dashboard/summary",
                timeout_seconds,
                "clickhouse accounting summary",
            )

    if "druid" in active_stacks:
        wait_for_json(
            "http://localhost:8081/health",
            lambda payload: isinstance(payload, dict) and payload.get("status") == "ok",
            timeout_seconds,
            "api druid health",
        )
        if run_producer_on_start:
            validate_backend_summary(
                "http://localhost:8081/api/v1/dashboard/summary",
                timeout_seconds,
                "druid accounting summary",
            )

    print("[done] startup smoke checks completed")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[error] {exc}", file=sys.stderr)
        raise SystemExit(1)