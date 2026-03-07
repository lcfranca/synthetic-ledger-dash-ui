#!/usr/bin/env python3

from __future__ import annotations

import json
import math
import os
import sys
import time
import urllib.error
import urllib.request


EXPECTED_ACCOUNT_ROLES = {
    "cash",
    "bank_accounts",
    "recoverable_tax",
    "inventory",
    "accounts_payable",
    "tax_payable",
    "revenue",
    "returns",
    "cogs",
    "marketplace_fees",
    "outbound_freight",
    "bank_fees",
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
    expenses = float(income_statement["expenses"])
    net_income = float(income_statement["net_income"])

    if not approx_equal(net_revenue, revenue - returns):
        raise RuntimeError(f"{label}: net_revenue != revenue - returns")
    if not approx_equal(net_income, net_revenue - expenses):
        raise RuntimeError(f"{label}: net_income != net_revenue - expenses")
    if not approx_equal(assets_total, liabilities_and_equity) or not approx_equal(difference, 0.0):
        raise RuntimeError(f"{label}: assets total does not match liabilities plus equity")


def validate_backend_summary(url: str, timeout_seconds: int, label: str) -> None:
    summary = wait_for_json(
        url,
        lambda payload: isinstance(payload, dict) and bool(payload.get("entries")),
        timeout_seconds,
        label,
    )
    validate_summary(summary, label)
    print(f"[ok] {label} arithmetic validated")


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