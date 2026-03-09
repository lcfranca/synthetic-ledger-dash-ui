#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
import time
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any


def percentile(values: list[float], ratio: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return values[0]
    ordered = sorted(values)
    index = (len(ordered) - 1) * ratio
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
      return ordered[lower]
    weight = index - lower
    return ordered[lower] * (1.0 - weight) + ordered[upper] * weight


def fetch(url: str) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return response.status, response.read()


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    durations = [float(sample["elapsed_ms"]) for sample in samples if sample.get("ok")]
    sizes = [int(sample["response_bytes"]) for sample in samples if sample.get("ok")]
    return {
        "count": len(samples),
        "success_count": sum(1 for sample in samples if sample.get("ok")),
        "error_count": sum(1 for sample in samples if not sample.get("ok")),
        "min_ms": min(durations) if durations else None,
        "avg_ms": sum(durations) / len(durations) if durations else None,
        "p50_ms": percentile(durations, 0.50),
        "p95_ms": percentile(durations, 0.95),
        "p99_ms": percentile(durations, 0.99),
        "max_ms": max(durations) if durations else None,
        "avg_response_bytes": sum(sizes) / len(sizes) if sizes else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", required=True)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--duration-seconds", type=int, default=90)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    endpoints = [
        ("health", f"{args.base_url}/health"),
        ("summary", f"{args.base_url}/api/v1/dashboard/summary"),
        ("workspace", f"{args.base_url}/api/v1/dashboard/workspace"),
        ("entries", f"{args.base_url}/api/v1/dashboard/entries?limit=50"),
        ("filter_search", f"{args.base_url}/api/v1/dashboard/filter-search?field=product_name&query=a&limit=20"),
    ]

    started = time.monotonic()
    deadline = started + max(args.duration_seconds, 1)
    samples: list[dict[str, Any]] = []
    index = 0

    while time.monotonic() < deadline:
        endpoint_name, endpoint_url = endpoints[index % len(endpoints)]
        index += 1
        sample_started = time.perf_counter()
        sample: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "backend": args.backend,
            "endpoint": endpoint_name,
            "url": endpoint_url,
        }
        try:
            status_code, payload = fetch(endpoint_url)
            elapsed_ms = (time.perf_counter() - sample_started) * 1000.0
            sample.update(
                {
                    "ok": True,
                    "status_code": status_code,
                    "elapsed_ms": elapsed_ms,
                    "response_bytes": len(payload),
                }
            )
            try:
                decoded = json.loads(payload.decode("utf-8"))
                if isinstance(decoded, dict):
                    sample["payload_observations"] = {
                        "status": decoded.get("status"),
                        "backend": decoded.get("backend"),
                        "timestamp": decoded.get("timestamp"),
                        "entry_count": len(decoded.get("entries", [])) if isinstance(decoded.get("entries"), list) else None,
                    }
            except Exception:
                sample["payload_observations"] = None
        except urllib.error.HTTPError as exc:
            sample.update(
                {
                    "ok": False,
                    "status_code": exc.code,
                    "elapsed_ms": (time.perf_counter() - sample_started) * 1000.0,
                    "response_bytes": 0,
                    "error": str(exc),
                }
            )
        except Exception as exc:
            sample.update(
                {
                    "ok": False,
                    "status_code": None,
                    "elapsed_ms": (time.perf_counter() - sample_started) * 1000.0,
                    "response_bytes": 0,
                    "error": str(exc),
                }
            )
        samples.append(sample)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample["endpoint"])].append(sample)

    payload = {
        "backend": args.backend,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": args.duration_seconds,
        "sample_count": len(samples),
        "endpoints": {name: summarize(endpoint_samples) for name, endpoint_samples in grouped.items()},
        "samples": samples,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())