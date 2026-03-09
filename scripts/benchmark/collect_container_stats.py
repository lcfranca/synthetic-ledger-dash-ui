#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
import subprocess
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
PROJECT_NAME = ROOT.name

SIZE_UNITS = {
    "b": 1,
    "kb": 1000,
    "mb": 1000**2,
    "gb": 1000**3,
    "tb": 1000**4,
    "kib": 1024,
    "mib": 1024**2,
    "gib": 1024**3,
    "tib": 1024**4,
}


def parse_percent(text: str) -> float:
    return float(str(text).replace("%", "").strip() or 0.0)


def parse_bytes(text: str) -> float:
    match = re.match(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)\s*", text)
    if not match:
        return 0.0
    value = float(match.group(1))
    unit = match.group(2).lower()
    return value * SIZE_UNITS.get(unit, 1)


def current_container_ids() -> list[str]:
    completed = subprocess.run(
        ["docker", "ps", "--filter", f"label=com.docker.compose.project={PROJECT_NAME}", "--format", "{{.ID}}"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return [line.strip() for line in completed.stdout.splitlines() if line.strip()]


def sample_stats(container_ids: list[str]) -> list[dict[str, Any]]:
    if not container_ids:
        return []
    completed = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", *container_ids],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    rows: list[dict[str, Any]] = []
    for line in completed.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        memory_usage = str(row.get("MemUsage", "0B / 0B")).split("/")
        net_io = str(row.get("NetIO", "0B / 0B")).split("/")
        block_io = str(row.get("BlockIO", "0B / 0B")).split("/")
        rows.append(
            {
                "container": row.get("Name"),
                "cpu_percent": parse_percent(str(row.get("CPUPerc", "0%"))),
                "memory_used_bytes": parse_bytes(memory_usage[0]),
                "memory_limit_bytes": parse_bytes(memory_usage[1]) if len(memory_usage) > 1 else 0.0,
                "network_rx_bytes": parse_bytes(net_io[0]) if net_io else 0.0,
                "network_tx_bytes": parse_bytes(net_io[1]) if len(net_io) > 1 else 0.0,
                "block_read_bytes": parse_bytes(block_io[0]) if block_io else 0.0,
                "block_write_bytes": parse_bytes(block_io[1]) if len(block_io) > 1 else 0.0,
                "pids": int(str(row.get("PIDs", "0") or 0)),
            }
        )
    return rows


def summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    cpu = [float(sample["cpu_percent"]) for sample in samples]
    memory_mb = [float(sample["memory_used_bytes"]) / (1024 * 1024) for sample in samples]
    return {
        "sample_count": len(samples),
        "cpu_avg": sum(cpu) / len(cpu) if cpu else None,
        "cpu_peak": max(cpu) if cpu else None,
        "memory_avg_mb": sum(memory_mb) / len(memory_mb) if memory_mb else None,
        "memory_peak_mb": max(memory_mb) if memory_mb else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=int, default=270)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    samples: list[dict[str, Any]] = []
    deadline = time.monotonic() + max(args.duration_seconds, 1)

    while time.monotonic() < deadline:
        for row in sample_stats(current_container_ids()):
            row["timestamp"] = datetime.now(timezone.utc).isoformat()
            samples.append(row)
        time.sleep(max(args.interval_seconds, 1.0))

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        grouped[str(sample["container"])].append(sample)

    payload = {
        "duration_seconds": args.duration_seconds,
        "interval_seconds": args.interval_seconds,
        "containers": {name: summarize(container_samples) for name, container_samples in grouped.items()},
        "samples": samples,
    }

    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())