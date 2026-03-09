#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any


def fetch_json(url: str) -> dict[str, Any] | list[Any]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_snapshot(url: str) -> dict[str, Any]:
    try:
        return {"ok": True, "payload": fetch_json(url)}
    except urllib.error.HTTPError as exc:
        return {
            "ok": False,
            "status_code": exc.code,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }
    except Exception as exc:
        return {
            "ok": False,
            "status_code": None,
            "error_type": exc.__class__.__name__,
            "error": str(exc),
        }


def api_port(backend: str) -> int:
    return {
        "clickhouse": 8080,
        "druid": 8081,
        "pinot": 8082,
        "materialize": 8084,
    }[backend]


def debug_url(backend: str) -> str:
    return {
        "clickhouse": "http://localhost:8092/debug/kafka-fanout",
        "druid": "http://localhost:8092/debug/druid-supervisor",
        "pinot": "http://localhost:8092/debug/pinot-realtime",
        "materialize": "http://localhost:8092/debug/materialize-bootstrap",
    }[backend]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    base_url = f"http://localhost:{api_port(args.backend)}"
    payload = {
        "captured_at": datetime.now(timezone.utc).isoformat(),
        "backend": args.backend,
        "snapshots": {
            "master_data_health": fetch_snapshot("http://localhost:8091/health"),
            "storage_writer_health": fetch_snapshot("http://localhost:8092/health"),
            "realtime_gateway_health": fetch_snapshot("http://localhost:8083/health"),
            "backend_health": fetch_snapshot(f"{base_url}/health"),
            "backend_summary": fetch_snapshot(f"{base_url}/api/v1/dashboard/summary"),
            "backend_workspace": fetch_snapshot(f"{base_url}/api/v1/dashboard/workspace"),
            "backend_entries": fetch_snapshot(f"{base_url}/api/v1/dashboard/entries?limit=20"),
            "backend_filter_options": fetch_snapshot(f"{base_url}/api/v1/dashboard/filter-options"),
            "backend_debug": fetch_snapshot(debug_url(args.backend)),
        },
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())