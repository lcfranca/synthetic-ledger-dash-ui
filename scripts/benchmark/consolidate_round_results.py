#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def nested_get(payload: dict[str, Any], *path: str) -> Any:
    current: Any = payload
    for part in path:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--round-dir", required=True)
    args = parser.parse_args()

    round_dir = Path(args.round_dir)
    metadata = load_json(round_dir / "metadata.json")
    api_latencies = load_json(round_dir / "api_latencies.json")
    sql_latencies = load_json(round_dir / "sql_latencies.json")
    ws_metrics = load_json(round_dir / "ws_metrics.json")
    resources = load_json(round_dir / "resources.json")
    health_timeline = load_json(round_dir / "health_timeline.json")
    debug_snapshots = load_json(round_dir / "debug_snapshots.json")

    workspace_snapshot = nested_get(debug_snapshots, "snapshots", "backend_workspace") or {}
    workspace_summary = nested_get(workspace_snapshot, "payload", "summary") or {}
    balance_sheet = workspace_summary.get("balance_sheet", {}) if isinstance(workspace_summary, dict) else {}

    round_report = {
        "metadata": metadata,
        "api_latencies": api_latencies,
        "sql_latencies": sql_latencies,
        "ws_metrics": ws_metrics,
        "resources": resources,
        "health_timeline": health_timeline,
        "debug_snapshots": debug_snapshots,
        "derived_metrics": {
            "balance_sheet_difference": nested_get(balance_sheet, "difference"),
            "api_summary_p95_ms": nested_get(api_latencies, "endpoints", "summary", "p95_ms"),
            "api_workspace_p95_ms": nested_get(api_latencies, "endpoints", "workspace", "p95_ms"),
            "sql_entries_count_p95_ms": nested_get(sql_latencies, "queries", "entries_count", "p95_ms"),
            "sql_summary_by_role_p95_ms": nested_get(sql_latencies, "queries", "summary_by_role", "p95_ms"),
            "frontend_time_to_first_meaningful_state_ms": nested_get(ws_metrics, "metrics", "frontend_time_to_first_meaningful_state_ms"),
            "snapshot_rate_per_second": nested_get(ws_metrics, "metrics", "snapshot_rate_per_second"),
            "entry_rate_per_second": nested_get(ws_metrics, "metrics", "entry_rate_per_second"),
            "health_transition_total": sum(int(value) for value in (health_timeline.get("transition_count") or {}).values()),
        },
    }

    with open(round_dir / "round_report.json", "w", encoding="utf-8") as handle:
        json.dump(round_report, handle, indent=2)

    summary_row = {
        "round_id": metadata.get("round_id"),
        "commit": metadata.get("commit"),
        "backend": metadata.get("backend"),
        "scenario": metadata.get("scenario"),
        "run_number": metadata.get("run_number"),
        "started_at": metadata.get("started_at"),
        "duration_seconds": metadata.get("duration_seconds"),
        "api_summary_p95_ms": round_report["derived_metrics"]["api_summary_p95_ms"],
        "api_workspace_p95_ms": round_report["derived_metrics"]["api_workspace_p95_ms"],
        "sql_entries_count_p95_ms": round_report["derived_metrics"]["sql_entries_count_p95_ms"],
        "sql_summary_by_role_p95_ms": round_report["derived_metrics"]["sql_summary_by_role_p95_ms"],
        "frontend_time_to_first_meaningful_state_ms": round_report["derived_metrics"]["frontend_time_to_first_meaningful_state_ms"],
        "snapshot_rate_per_second": round_report["derived_metrics"]["snapshot_rate_per_second"],
        "entry_rate_per_second": round_report["derived_metrics"]["entry_rate_per_second"],
        "balance_sheet_difference": round_report["derived_metrics"]["balance_sheet_difference"],
        "health_transition_total": round_report["derived_metrics"]["health_transition_total"],
    }

    with open(round_dir / "summary.csv", "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(summary_row.keys()))
        writer.writeheader()
        writer.writerow(summary_row)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())