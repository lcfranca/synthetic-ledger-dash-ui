#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def fetch(url: str) -> dict[str, Any] | list[Any] | None:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=8) as response:
        return json.loads(response.read().decode("utf-8"))


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


def extract_state(payload: Any) -> str | None:
    if isinstance(payload, dict):
        for key in ("status", "state"):
            value = payload.get(key)
            if value is not None:
                return str(value)
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--duration-seconds", type=int, default=270)
    parser.add_argument("--interval-seconds", type=float, default=2.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    endpoints = {
        "master_data": "http://localhost:8091/health",
        "storage_writer": "http://localhost:8092/health",
        "realtime_gateway": "http://localhost:8083/health",
        "backend_health": f"http://localhost:{api_port(args.backend)}/health",
        "backend_debug": debug_url(args.backend),
    }

    deadline = time.monotonic() + max(args.duration_seconds, 1)
    samples: list[dict[str, Any]] = []
    transitions: dict[str, int] = defaultdict(int)
    previous_states: dict[str, str | None] = {}

    while time.monotonic() < deadline:
        for endpoint_name, url in endpoints.items():
            sample: dict[str, Any] = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "endpoint": endpoint_name,
                "url": url,
            }
            try:
                payload = fetch(url)
                state = extract_state(payload)
                sample.update({"ok": True, "state": state, "payload": payload})
                if endpoint_name in previous_states and previous_states[endpoint_name] != state:
                    transitions[endpoint_name] += 1
                previous_states[endpoint_name] = state
            except urllib.error.HTTPError as exc:
                sample.update({"ok": False, "state": None, "error": str(exc), "status_code": exc.code})
            except Exception as exc:
                sample.update({"ok": False, "state": None, "error": str(exc)})
            samples.append(sample)
        time.sleep(max(args.interval_seconds, 0.25))

    payload = {
        "backend": args.backend,
        "duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval_seconds,
        "transition_count": dict(transitions),
        "samples": samples,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())