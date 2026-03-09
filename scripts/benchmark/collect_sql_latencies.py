#!/usr/bin/env python3

from __future__ import annotations

import argparse
import base64
import json
import math
import os
import subprocess
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]


def read_env_value(env_file: str, key: str) -> str | None:
    for line in Path(env_file).read_text(encoding="utf-8").splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        current_key, current_value = line.split("=", 1)
        if current_key.strip() == key:
            return current_value.strip()
    return None


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = (len(ordered) - 1) * ratio
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(sample["elapsed_ms"]) for sample in samples if sample.get("ok")]
    row_counts = [int(sample.get("row_count", 0) or 0) for sample in samples if sample.get("ok")]
    return {
        "count": len(samples),
        "success_count": sum(1 for sample in samples if sample.get("ok")),
        "error_count": sum(1 for sample in samples if not sample.get("ok")),
        "p50_ms": percentile(durations, 0.50),
        "p95_ms": percentile(durations, 0.95),
        "p99_ms": percentile(durations, 0.99),
        "min_ms": min(durations) if durations else None,
        "max_ms": max(durations) if durations else None,
        "avg_ms": sum(durations) / len(durations) if durations else None,
        "avg_row_count": sum(row_counts) / len(row_counts) if row_counts else None,
    }


def post_json(url: str, payload: dict[str, Any]) -> tuple[dict[str, Any], int]:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return json.loads(raw.decode("utf-8")), len(raw)


def get_text(url: str) -> tuple[str, int]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return raw.decode("utf-8"), len(raw)


def get_text_with_headers(url: str, headers: dict[str, str]) -> tuple[str, int]:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=20) as response:
        raw = response.read()
        return raw.decode("utf-8"), len(raw)


def clickhouse_auth_headers(env_file: str) -> dict[str, str]:
    username = read_env_value(env_file, "CLICKHOUSE_READONLY_USER") or read_env_value(env_file, "CLICKHOUSE_USER")
    password = read_env_value(env_file, "CLICKHOUSE_READONLY_PASSWORD") or read_env_value(env_file, "CLICKHOUSE_PASSWORD") or ""
    if not username:
        return {"Accept": "application/json"}
    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return {
        "Accept": "application/json",
        "Authorization": f"Basic {token}",
    }


def run_materialize_query(env_file: str, query: str) -> dict[str, Any]:
    materialize_url = read_env_value(env_file, "MATERIALIZE_URL")
    if not materialize_url:
        raise RuntimeError(f"MATERIALIZE_URL not found in env file: {env_file}")
    code = (
        "import json, os, time, psycopg; "
        "start=time.perf_counter(); "
        "conn=psycopg.connect(os.environ['MATERIALIZE_URL']); "
        "cur=conn.cursor(); "
        "cur.execute(os.environ['BENCHMARK_SQL_QUERY']); "
        "rows=cur.fetchall(); "
        "elapsed=(time.perf_counter()-start)*1000.0; "
        "print(json.dumps({'elapsed_ms': elapsed, 'row_count': len(rows), 'preview': rows[:5]}, default=str))"
    )
    env = os.environ.copy()
    env["BENCHMARK_SQL_QUERY"] = query
    completed = subprocess.run(
        [
            "docker",
            "compose",
            "--env-file",
            env_file,
            "exec",
            "-T",
            "-e",
            f"MATERIALIZE_URL={materialize_url}",
            "-e",
            f"BENCHMARK_SQL_QUERY={query}",
            "api-materialize",
            "python3",
            "-c",
            code,
        ],
        cwd=str(ROOT),
        env=os.environ.copy(),
        text=True,
        capture_output=True,
        check=True,
    )
    return json.loads(completed.stdout.strip())


def run_query(backend: str, env_file: str, query_name: str, query: str) -> tuple[dict[str, Any], int]:
    if backend == "clickhouse":
        encoded = urllib.parse.quote(query, safe="")
        payload, size = get_text_with_headers(
            f"http://localhost:8123/?query={encoded}",
            clickhouse_auth_headers(env_file),
        )
        return {"row_count": max(len([line for line in payload.splitlines() if line.strip()]), 0)}, size
    if backend == "druid":
        response, size = post_json("http://localhost:8889/druid/v2/sql", {"query": query})
        return {"row_count": len(response), "preview": response[:5] if isinstance(response, list) else response}, size
    if backend == "pinot":
        response, size = post_json("http://localhost:8099/query/sql", {"sql": query})
        rows = (((response.get("resultTable") or {}).get("rows")) or []) if isinstance(response, dict) else []
        return {"row_count": len(rows), "preview": rows[:5]}, size
    if backend == "materialize":
        response = run_materialize_query(env_file, query)
        return response, len(json.dumps(response).encode("utf-8"))
    raise RuntimeError(f"unsupported backend for sql collector: {backend}")


def query_catalog(backend: str) -> list[tuple[str, str]]:
    if backend == "clickhouse":
        return [
            ("entries_count", "SELECT count() AS c FROM ledger.entries FORMAT JSONEachRow"),
            ("summary_by_role", "SELECT account_role, sum(signed_amount) AS signed_amount FROM ledger.entries GROUP BY account_role ORDER BY account_role LIMIT 32 FORMAT JSONEachRow"),
            ("filtered_entries", "SELECT entry_id, account_code, signed_amount FROM ledger.entries WHERE product_name != '' ORDER BY ingested_at DESC LIMIT 50 FORMAT JSONEachRow"),
        ]
    if backend == "druid":
        return [
            ("entries_count", 'SELECT COUNT(*) AS c FROM "ledger_events"'),
            ("summary_by_role", 'SELECT account_role, SUM(signed_amount) AS signed_amount FROM "ledger_events" GROUP BY account_role ORDER BY account_role LIMIT 32'),
            ("filtered_entries", "SELECT entry_id, account_code, signed_amount FROM \"ledger_events\" WHERE product_name <> '' ORDER BY ingested_at DESC LIMIT 50"),
        ]
    if backend == "pinot":
        return [
            ("entries_count", "SELECT COUNT(*) AS c FROM ledger_events"),
            ("summary_by_role", "SELECT account_role, SUM(signed_amount) AS signed_amount FROM ledger_events GROUP BY account_role LIMIT 32"),
            ("filtered_entries", "SELECT entry_id, account_code, signed_amount FROM ledger_events WHERE product_name <> '' LIMIT 50"),
        ]
    if backend == "materialize":
        return [
            ("entries_count", "SELECT COUNT(*) AS c FROM public.ledger_entries_current_mv"),
            ("summary_by_role", "SELECT account_role, statement_section, signed_amount, entry_count FROM public.ledger_summary_by_role_mv ORDER BY account_role LIMIT 32"),
            ("filtered_entries", "SELECT entry_id, account_code, signed_amount FROM public.ledger_entries_current_mv WHERE product_name <> '' ORDER BY ingested_at DESC LIMIT 50"),
        ]
    raise RuntimeError(f"unsupported backend: {backend}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--env-file", required=True)
    parser.add_argument("--duration-seconds", type=int, default=90)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    catalog = query_catalog(args.backend)
    samples: list[dict[str, Any]] = []
    started = time.monotonic()
    deadline = started + max(args.duration_seconds, 1)
    index = 0

    while time.monotonic() < deadline:
        query_name, query = catalog[index % len(catalog)]
        index += 1
        started_sample = time.perf_counter()
        sample: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "backend": args.backend,
            "query_name": query_name,
            "query": query,
        }
        try:
            response, response_bytes = run_query(args.backend, args.env_file, query_name, query)
            elapsed_ms = float(response.get("elapsed_ms", (time.perf_counter() - started_sample) * 1000.0))
            sample.update(
                {
                    "ok": True,
                    "elapsed_ms": elapsed_ms,
                    "row_count": int(response.get("row_count", 0) or 0),
                    "response_bytes": response_bytes,
                    "preview": response.get("preview"),
                }
            )
        except Exception as exc:
            sample.update(
                {
                    "ok": False,
                    "elapsed_ms": (time.perf_counter() - started_sample) * 1000.0,
                    "row_count": 0,
                    "response_bytes": 0,
                    "error": str(exc),
                    "error_type": exc.__class__.__name__,
                    "stderr": getattr(exc, "stderr", None),
                }
            )
        samples.append(sample)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample["query_name"])].append(sample)

    payload = {
        "backend": args.backend,
        "duration_seconds": args.duration_seconds,
        "sample_count": len(samples),
        "queries": {name: summarize(query_samples) for name, query_samples in grouped.items()},
        "samples": samples,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())