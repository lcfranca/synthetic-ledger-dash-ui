#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


PROJECT_PREFIX = "syntetic-ledger-dash-ui-"
CANONICAL_SCENARIO = "report-conclusion"


@dataclass(frozen=True)
class RoundArtifact:
    path: Path
    payload: dict[str, Any]
    metadata: dict[str, Any]
    started_at: datetime

    @property
    def round_id(self) -> str:
        return str(self.metadata["round_id"])

    @property
    def backend(self) -> str:
        return str(self.metadata["backend"])

    @property
    def scenario(self) -> str:
        return str(self.metadata["scenario"])


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    return datetime.fromisoformat(normalized).astimezone(UTC)


def load_rounds(artifacts_dir: Path) -> list[RoundArtifact]:
    rounds: list[RoundArtifact] = []
    for round_dir in sorted(artifacts_dir.iterdir()):
        report_path = round_dir / "round_report.json"
        if not report_path.exists():
            continue
        payload = json.loads(report_path.read_text(encoding="utf-8"))
        metadata = payload["metadata"]
        started_at = parse_timestamp(metadata.get("started_at"))
        if started_at is None:
            continue
        rounds.append(
            RoundArtifact(
                path=round_dir,
                payload=payload,
                metadata=metadata,
                started_at=started_at,
            )
        )
    return rounds


def canonical_rounds(rounds: Iterable[RoundArtifact]) -> dict[str, RoundArtifact]:
    selected: dict[str, RoundArtifact] = {}
    for artifact in rounds:
        if artifact.scenario != CANONICAL_SCENARIO:
            continue
        current = selected.get(artifact.backend)
        if current is None or artifact.started_at > current.started_at:
            selected[artifact.backend] = artifact
    return selected


def total_probe_errors(artifact: RoundArtifact) -> int:
    total = 0
    for stats in artifact.payload["api_latencies"]["endpoints"].values():
        total += int(stats.get("error_count") or 0)
    for stats in artifact.payload["sql_latencies"]["queries"].values():
        total += int(stats.get("error_count") or 0)
    return total


def health_transitions_total(artifact: RoundArtifact) -> int:
    transitions = artifact.payload["health_timeline"].get("transition_count") or {}
    return sum(int(value) for value in transitions.values())


def classify_round(artifact: RoundArtifact, canonical_ids: set[str]) -> str:
    if artifact.round_id in canonical_ids:
        return "canônica"
    if artifact.scenario.startswith("validation"):
        return "validação"
    if artifact.scenario == CANONICAL_SCENARIO:
        return "substituída"
    return artifact.scenario


def format_decimal(value: Any, digits: int = 2) -> str:
    if value is None:
        return "N/D"
    if isinstance(value, bool):
        return "sim" if value else "não"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return f"{value:.{digits}f}".replace(".", ",")
    return str(value)


def latex_escape(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def latex_breakable(value: Any) -> str:
    text = str(value)
    escaped = text.replace("\\", "/")
    escaped = escaped.replace("{", "\\{").replace("}", "\\}")
    return rf"\nolinkurl{{{escaped}}}"


def format_cell(value: Any, *, mode: str = "text") -> str:
    if mode == "literal":
        return str(value)
    if mode == "breakable":
        return latex_breakable(value)
    return latex_escape(value)


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_longtable(
    caption: str,
    label: str,
    headers: list[str],
    rows: list[list[Any]],
    column_spec: str,
    *,
    size_command: str = r"\scriptsize",
    landscape: bool = False,
) -> str:
    escaped_headers = [latex_escape(header) for header in headers]
    rendered_rows = []
    for row in rows:
        rendered_cells = [cell if isinstance(cell, str) and cell.startswith("\\") else latex_escape(cell) for cell in row]
        rendered_rows.append(" & ".join(rendered_cells) + r" \\")
    header_line = " & ".join(escaped_headers) + r" \\"
    body = "\n".join(rendered_rows)
    prefix = "\\begin{landscape}\n" if landscape else ""
    suffix = "\\end{landscape}\n" if landscape else ""
    return f"""{prefix}{size_command}
\\setlength{{\\LTleft}}{{0pt}}
\\setlength{{\\LTright}}{{0pt}}
\\setlength{{\\tabcolsep}}{{4pt}}
\\begin{{longtable}}{{{column_spec}}}
\\caption{{{latex_escape(caption)}}}\\label{{{label}}}\\\\
\\toprule
{header_line}\\midrule
\\endfirsthead
\\toprule
{header_line}\\midrule
\\endhead
{body}
\\bottomrule
\\end{{longtable}}
\\normalsize
{suffix}
"""


def render_backend_resource_tables(resource_details: list[dict[str, Any]]) -> list[str]:
    sections: list[str] = []
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in resource_details:
        grouped[str(row["backend"])].append(row)

    for backend in sorted(grouped):
        title = backend.capitalize()
        sections.append(f"### Backend {title}")
        sections.append(
            render_longtable(
                f"Detalhamento de recursos por papel de serviço para {title}.",
                f"tab:resource-details-{backend}",
                [
                    "Papel",
                    "Contêiner",
                    "CPU média",
                    "CPU pico",
                    "Memória média MB",
                    "Memória pico MB",
                    "Amostras",
                ],
                [
                    [
                        format_cell(row["role"], mode="breakable"),
                        format_cell(row["container"], mode="breakable"),
                        format_decimal(row["cpu_avg"], 4),
                        format_decimal(row["cpu_peak"], 4),
                        format_decimal(row["memory_avg_mb"], 2),
                        format_decimal(row["memory_peak_mb"], 2),
                        row["sample_count"],
                    ]
                    for row in grouped[backend]
                ],
                "L{2.4cm}L{8.6cm}rrrrr",
                landscape=True,
            )
        )
    return sections


def sample_offset_ms(reference: datetime, sample_timestamp: str | None) -> int | None:
    sample_time = parse_timestamp(sample_timestamp)
    if sample_time is None:
        return None
    delta = sample_time - reference
    return int(delta.total_seconds() * 1000)


def first_api_success_ms(artifact: RoundArtifact, endpoint: str) -> int | None:
    for sample in artifact.payload["api_latencies"]["samples"]:
        if sample.get("endpoint") != endpoint:
            continue
        if sample.get("ok"):
            return sample_offset_ms(artifact.started_at, sample.get("timestamp"))
    return None


def first_positive_entry_count_ms(artifact: RoundArtifact, endpoint: str) -> int | None:
    for sample in artifact.payload["api_latencies"]["samples"]:
        if sample.get("endpoint") != endpoint or not sample.get("ok"):
            continue
        observations = sample.get("payload_observations") or {}
        entry_count = observations.get("entry_count")
        if isinstance(entry_count, (int, float)) and entry_count > 0:
            return sample_offset_ms(artifact.started_at, sample.get("timestamp"))
    return None


def first_sql_success_ms(artifact: RoundArtifact, query_name: str) -> int | None:
    for sample in artifact.payload["sql_latencies"]["samples"]:
        if sample.get("query_name") != query_name:
            continue
        if sample.get("ok"):
            return sample_offset_ms(artifact.started_at, sample.get("timestamp"))
    return None


def summarize_health(artifact: RoundArtifact) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sample in artifact.payload["health_timeline"]["samples"]:
        grouped[str(sample.get("endpoint"))].append(sample)

    transitions = artifact.payload["health_timeline"].get("transition_count") or {}
    rows: list[dict[str, Any]] = []
    for endpoint in sorted(grouped):
        samples = grouped[endpoint]
        first_ok_ms = None
        states_seen: list[str] = []
        seen = set()
        non_ok_samples = 0
        for sample in samples:
            state = str(sample.get("state") or "desconhecido")
            if state not in seen:
                seen.add(state)
                states_seen.append(state)
            is_ok = bool(sample.get("ok")) and state == "ok"
            if is_ok and first_ok_ms is None:
                first_ok_ms = sample_offset_ms(artifact.started_at, sample.get("timestamp"))
            if not is_ok:
                non_ok_samples += 1
        rows.append(
            {
                "backend": artifact.backend,
                "endpoint": endpoint,
                "sample_count": len(samples),
                "non_ok_samples": non_ok_samples,
                "first_ok_ms": first_ok_ms,
                "transitions": int(transitions.get(endpoint) or 0),
                "states_seen": " | ".join(states_seen),
            }
        )
    return rows


def summarize_debug_snapshots(artifact: RoundArtifact) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    snapshots = artifact.payload["debug_snapshots"].get("snapshots") or {}
    for snapshot_name, snapshot_payload in sorted(snapshots.items()):
        payload = snapshot_payload.get("payload") or {}
        rows.append(
            {
                "backend": artifact.backend,
                "snapshot": snapshot_name,
                "ok": bool(snapshot_payload.get("ok")),
                "payload_field_count": len(payload) if isinstance(payload, dict) else 0,
                "has_timestamp": isinstance(payload, dict) and "timestamp" in payload,
                "has_entries": isinstance(payload, dict) and "entries" in payload,
                "has_balance_sheet": isinstance(payload, dict) and "balance_sheet" in payload,
            }
        )
    return rows


def container_role(container_name: str, backend: str) -> str:
    short_name = container_name
    if short_name.startswith(PROJECT_PREFIX):
        short_name = short_name[len(PROJECT_PREFIX) :]
    if short_name.endswith("-1"):
        short_name = short_name[:-2]
    if short_name == backend:
        return f"engine:{backend}"
    return short_name


def summarize_resource_totals(artifact: RoundArtifact) -> dict[str, Any]:
    containers = artifact.payload["resources"].get("containers") or {}
    total_memory_avg = 0.0
    total_memory_peak = 0.0
    total_cpu_avg = 0.0
    peak_cpu = 0.0
    peak_memory = 0.0
    for stats in containers.values():
        total_memory_avg += float(stats.get("memory_avg_mb") or 0.0)
        total_memory_peak += float(stats.get("memory_peak_mb") or 0.0)
        total_cpu_avg += float(stats.get("cpu_avg") or 0.0)
        peak_cpu = max(peak_cpu, float(stats.get("cpu_peak") or 0.0))
        peak_memory = max(peak_memory, float(stats.get("memory_peak_mb") or 0.0))
    return {
        "backend": artifact.backend,
        "container_count": len(containers),
        "total_cpu_avg": total_cpu_avg,
        "peak_cpu": peak_cpu,
        "total_memory_avg_mb": total_memory_avg,
        "total_memory_peak_mb": total_memory_peak,
        "peak_container_memory_mb": peak_memory,
    }


def summarize_resource_details(artifact: RoundArtifact) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    containers = artifact.payload["resources"].get("containers") or {}
    for container_name, stats in sorted(containers.items()):
        rows.append(
            {
                "backend": artifact.backend,
                "role": container_role(container_name, artifact.backend),
                "container": container_name,
                "cpu_avg": stats.get("cpu_avg"),
                "cpu_peak": stats.get("cpu_peak"),
                "memory_avg_mb": stats.get("memory_avg_mb"),
                "memory_peak_mb": stats.get("memory_peak_mb"),
                "sample_count": stats.get("sample_count"),
            }
        )
    return rows


def round_inventory_rows(rounds: list[RoundArtifact], canonical_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in sorted(rounds, key=lambda item: item.started_at):
        rows.append(
            {
                "classificacao": classify_round(artifact, canonical_ids),
                "backend": artifact.backend,
                "cenario": artifact.scenario,
                "round_id": artifact.round_id,
                "started_at": artifact.metadata.get("started_at"),
                "duration_seconds": artifact.metadata.get("duration_seconds"),
                "total_probe_errors": total_probe_errors(artifact),
                "health_transition_total": health_transitions_total(artifact),
                "balance_sheet_difference": artifact.payload["derived_metrics"].get("balance_sheet_difference"),
            }
        )
    return rows


def api_latency_rows(canonical: list[RoundArtifact]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in canonical:
        for endpoint, stats in artifact.payload["api_latencies"]["endpoints"].items():
            rows.append(
                {
                    "backend": artifact.backend,
                    "endpoint": endpoint,
                    "count": stats.get("count"),
                    "success_count": stats.get("success_count"),
                    "error_count": stats.get("error_count"),
                    "avg_ms": stats.get("avg_ms"),
                    "p50_ms": stats.get("p50_ms"),
                    "p95_ms": stats.get("p95_ms"),
                    "p99_ms": stats.get("p99_ms"),
                    "max_ms": stats.get("max_ms"),
                    "avg_response_bytes": stats.get("avg_response_bytes"),
                }
            )
    return rows


def sql_latency_rows(canonical: list[RoundArtifact]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in canonical:
        for query_name, stats in artifact.payload["sql_latencies"]["queries"].items():
            rows.append(
                {
                    "backend": artifact.backend,
                    "query_name": query_name,
                    "count": stats.get("count"),
                    "success_count": stats.get("success_count"),
                    "error_count": stats.get("error_count"),
                    "avg_row_count": stats.get("avg_row_count"),
                    "avg_ms": stats.get("avg_ms"),
                    "p50_ms": stats.get("p50_ms"),
                    "p95_ms": stats.get("p95_ms"),
                    "p99_ms": stats.get("p99_ms"),
                    "max_ms": stats.get("max_ms"),
                }
            )
    return rows


def readiness_rows(canonical: list[RoundArtifact]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in canonical:
        rows.append(
            {
                "backend": artifact.backend,
                "api_summary_first_success_ms": first_api_success_ms(artifact, "summary"),
                "api_workspace_first_success_ms": first_api_success_ms(artifact, "workspace"),
                "api_entries_first_success_ms": first_api_success_ms(artifact, "entries"),
                "summary_positive_entry_count_ms": first_positive_entry_count_ms(artifact, "summary"),
                "workspace_positive_entry_count_ms": first_positive_entry_count_ms(artifact, "workspace"),
                "sql_entries_count_first_success_ms": first_sql_success_ms(artifact, "entries_count"),
                "sql_summary_by_role_first_success_ms": first_sql_success_ms(artifact, "summary_by_role"),
                "sql_filtered_entries_first_success_ms": first_sql_success_ms(artifact, "filtered_entries"),
            }
        )
    return rows


def websocket_rows(canonical: list[RoundArtifact]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in canonical:
        metrics = artifact.payload["ws_metrics"]["metrics"]
        counts = artifact.payload["ws_metrics"].get("counts") or {}
        rows.append(
            {
                "backend": artifact.backend,
                "frontend_time_to_first_meaningful_state_ms": metrics.get("frontend_time_to_first_meaningful_state_ms"),
                "first_snapshot_visible_ms": metrics.get("first_snapshot_visible_ms"),
                "entry_to_queue_visible_ms": metrics.get("entry_to_queue_visible_ms"),
                "event_to_snapshot_visible_ms": metrics.get("event_to_snapshot_visible_ms"),
                "sale_to_sales_workspace_visible_ms": metrics.get("sale_to_sales_workspace_visible_ms"),
                "snapshot_rate_per_second": metrics.get("snapshot_rate_per_second"),
                "entry_rate_per_second": metrics.get("entry_rate_per_second"),
                "snapshot_count": counts.get("dashboard.snapshot"),
                "entry_created_count": counts.get("entry.created"),
            }
        )
    return rows


def failure_rows(rounds: list[RoundArtifact], canonical_ids: set[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for artifact in sorted(rounds, key=lambda item: item.started_at):
        classification = classify_round(artifact, canonical_ids)
        for probe_type, probes in (
            ("api", artifact.payload["api_latencies"]["endpoints"]),
            ("sql", artifact.payload["sql_latencies"]["queries"]),
        ):
            for probe_name, stats in probes.items():
                error_count = int(stats.get("error_count") or 0)
                if error_count == 0:
                    continue
                rows.append(
                    {
                        "classificacao": classification,
                        "backend": artifact.backend,
                        "cenario": artifact.scenario,
                        "round_id": artifact.round_id,
                        "probe_type": probe_type,
                        "probe_name": probe_name,
                        "error_count": error_count,
                        "sample_count": stats.get("count"),
                        "success_count": stats.get("success_count"),
                        "p95_ms": stats.get("p95_ms"),
                    }
                )
    return rows


def write_markdown(output_path: Path, sections: list[str]) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n\n".join(sections).strip() + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts-dir", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    artifacts_dir = Path(args.artifacts_dir)
    output_dir = Path(args.output_dir)
    csv_dir = output_dir / "csv"

    rounds = load_rounds(artifacts_dir)
    selected = canonical_rounds(rounds)
    canonical = [selected[name] for name in sorted(selected)]
    canonical_ids = {artifact.round_id for artifact in canonical}

    inventory = round_inventory_rows(rounds, canonical_ids)
    budgets = [
        {
            "backend": artifact.backend,
            "round_id": artifact.round_id,
            "bootstrap_wait_s": artifact.metadata["phase_budget_seconds"].get("bootstrap_wait"),
            "backend_readiness_wait_s": artifact.metadata["phase_budget_seconds"].get("backend_readiness_wait"),
            "warmup_s": artifact.metadata["phase_budget_seconds"].get("warmup"),
            "per_probe_segment_s": artifact.metadata["phase_budget_seconds"].get("per_probe_segment"),
            "duration_seconds": artifact.metadata.get("duration_seconds"),
        }
        for artifact in canonical
    ]
    api_rows = api_latency_rows(canonical)
    sql_rows = sql_latency_rows(canonical)
    readiness = readiness_rows(canonical)
    websocket = websocket_rows(canonical)
    health = [row for artifact in canonical for row in summarize_health(artifact)]
    debug = [row for artifact in canonical for row in summarize_debug_snapshots(artifact)]
    resource_totals = [summarize_resource_totals(artifact) for artifact in canonical]
    resource_details = [row for artifact in canonical for row in summarize_resource_details(artifact)]
    failures = failure_rows(rounds, canonical_ids)

    write_csv(
        csv_dir / "corpus_inventory.csv",
        inventory,
        [
            "classificacao",
            "backend",
            "cenario",
            "round_id",
            "started_at",
            "duration_seconds",
            "total_probe_errors",
            "health_transition_total",
            "balance_sheet_difference",
        ],
    )
    write_csv(
        csv_dir / "canonical_phase_budgets.csv",
        budgets,
        [
            "backend",
            "round_id",
            "bootstrap_wait_s",
            "backend_readiness_wait_s",
            "warmup_s",
            "per_probe_segment_s",
            "duration_seconds",
        ],
    )
    write_csv(
        csv_dir / "canonical_api_latency.csv",
        api_rows,
        [
            "backend",
            "endpoint",
            "count",
            "success_count",
            "error_count",
            "avg_ms",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "max_ms",
            "avg_response_bytes",
        ],
    )
    write_csv(
        csv_dir / "canonical_sql_latency.csv",
        sql_rows,
        [
            "backend",
            "query_name",
            "count",
            "success_count",
            "error_count",
            "avg_row_count",
            "avg_ms",
            "p50_ms",
            "p95_ms",
            "p99_ms",
            "max_ms",
        ],
    )
    write_csv(
        csv_dir / "canonical_readiness.csv",
        readiness,
        list(readiness[0].keys()) if readiness else [],
    )
    write_csv(
        csv_dir / "canonical_websocket_metrics.csv",
        websocket,
        list(websocket[0].keys()) if websocket else [],
    )
    write_csv(
        csv_dir / "canonical_health_timeline.csv",
        health,
        list(health[0].keys()) if health else [],
    )
    write_csv(
        csv_dir / "canonical_debug_snapshots.csv",
        debug,
        list(debug[0].keys()) if debug else [],
    )
    write_csv(
        csv_dir / "canonical_resource_totals.csv",
        resource_totals,
        list(resource_totals[0].keys()) if resource_totals else [],
    )
    write_csv(
        csv_dir / "canonical_resource_details.csv",
        resource_details,
        list(resource_details[0].keys()) if resource_details else [],
    )
    write_csv(
        csv_dir / "round_failures.csv",
        failures,
        list(failures[0].keys()) if failures else [],
    )

    sections = [
        "# Resultados Comparativos Derivados dos Artefatos",
        (
            "Este capítulo é gerado automaticamente a partir dos artefatos em "
            "`artifacts/benchmark`. As tabelas abaixo não são mantidas manualmente: "
            "elas são reconstruídas no build do relatório, preservando rastreabilidade "
            "entre corpus empírico, tabelas e interpretação textual."
        ),
        "## Corpus, seleção canônica e rastreabilidade",
        (
            "A seleção canônica utiliza, para cada backend, a rodada mais recente do cenário "
            "`report-conclusion`. Rodadas auxiliares e tentativas substituídas permanecem "
            "documentadas para análise diagnóstica e para suporte a reruns de conformação."
        ),
        render_longtable(
            "Inventário completo das rodadas disponíveis no corpus de benchmark.",
            "tab:corpus-inventory",
            [
                "Classe",
                "Backend",
                "Cenário",
                "Round ID",
                "Início",
                "Duração (s)",
                "Erros",
                "Transições",
                "Dif. balanço",
            ],
            [
                [
                    row["classificacao"],
                    row["backend"],
                    row["cenario"],
                    format_cell(row["round_id"], mode="breakable"),
                    format_cell(row["started_at"], mode="breakable"),
                    row["duration_seconds"],
                    row["total_probe_errors"],
                    row["health_transition_total"],
                    format_decimal(row["balance_sheet_difference"]),
                ]
                for row in inventory
            ],
            "L{1.9cm}L{1.8cm}L{2.4cm}L{5.2cm}L{2.4cm}rrrr",
            landscape=True,
        ),
        render_longtable(
            "Orçamento de fases das rodadas canônicas utilizadas na comparação principal.",
            "tab:phase-budgets",
            [
                "Backend",
                "Round ID",
                "Bootstrap (s)",
                "Readiness (s)",
                "Warm-up (s)",
                "Segmento (s)",
                "Duração (s)",
            ],
            [
                [
                    row["backend"],
                    format_cell(row["round_id"], mode="breakable"),
                    row["bootstrap_wait_s"],
                    row["backend_readiness_wait_s"],
                    row["warmup_s"],
                    row["per_probe_segment_s"],
                    row["duration_seconds"],
                ]
                for row in budgets
            ],
            "L{1.8cm}L{7.0cm}rrrrr",
            landscape=True,
        ),
        "## Latência HTTP e SQL",
        render_longtable(
            "Latência HTTP por endpoint nas rodadas canônicas.",
            "tab:api-latency",
            [
                "Backend",
                "Endpoint",
                "Amostras",
                "Sucesso",
                "Erros",
                "Média ms",
                "p50 ms",
                "p95 ms",
                "p99 ms",
                "Máx ms",
                "Bytes médios",
            ],
            [
                [
                    row["backend"],
                    format_cell(row["endpoint"], mode="breakable"),
                    row["count"],
                    row["success_count"],
                    row["error_count"],
                    format_decimal(row["avg_ms"]),
                    format_decimal(row["p50_ms"]),
                    format_decimal(row["p95_ms"]),
                    format_decimal(row["p99_ms"]),
                    format_decimal(row["max_ms"]),
                    format_decimal(row["avg_response_bytes"]),
                ]
                for row in api_rows
            ],
            "L{1.8cm}L{2.3cm}rrrrrrrrr",
        ),
        render_longtable(
            "Latência SQL por consulta sintética nas rodadas canônicas.",
            "tab:sql-latency",
            [
                "Backend",
                "Consulta",
                "Amostras",
                "Sucesso",
                "Erros",
                "Linhas médias",
                "Média ms",
                "p50 ms",
                "p95 ms",
                "p99 ms",
                "Máx ms",
            ],
            [
                [
                    row["backend"],
                    format_cell(row["query_name"], mode="breakable"),
                    row["count"],
                    row["success_count"],
                    row["error_count"],
                    format_decimal(row["avg_row_count"]),
                    format_decimal(row["avg_ms"]),
                    format_decimal(row["p50_ms"]),
                    format_decimal(row["p95_ms"]),
                    format_decimal(row["p99_ms"]),
                    format_decimal(row["max_ms"]),
                ]
                for row in sql_rows
            ],
            "L{1.8cm}L{2.9cm}rrrrrrrrr",
        ),
        render_longtable(
            "Tempos até o primeiro sucesso observável de API e SQL nas rodadas canônicas.",
            "tab:readiness",
            [
                "Backend",
                "API summary",
                "API workspace",
                "API entries",
                "Summary > 0",
                "Workspace > 0",
                "SQL count",
                "SQL role",
                "SQL filtered",
            ],
            [
                [
                    row["backend"],
                    format_decimal(row["api_summary_first_success_ms"], 0),
                    format_decimal(row["api_workspace_first_success_ms"], 0),
                    format_decimal(row["api_entries_first_success_ms"], 0),
                    format_decimal(row["summary_positive_entry_count_ms"], 0),
                    format_decimal(row["workspace_positive_entry_count_ms"], 0),
                    format_decimal(row["sql_entries_count_first_success_ms"], 0),
                    format_decimal(row["sql_summary_by_role_first_success_ms"], 0),
                    format_decimal(row["sql_filtered_entries_first_success_ms"], 0),
                ]
                for row in readiness
            ],
            "p{1.8cm}rrrrrrrr",
        ),
        "## Convergência visual e experiência percebida",
        render_longtable(
            "Métricas de convergência visual e propagação de eventos nas rodadas canônicas.",
            "tab:websocket-metrics",
            [
                "Backend",
                "Meaningful",
                "1o snapshot",
                "Entry -> fila",
                "Evento -> snapshot",
                "Venda -> sales",
                "Snapshots/s",
                "Entries/s",
                "Snapshots",
                "Entry.created",
            ],
            [
                [
                    row["backend"],
                    format_decimal(row["frontend_time_to_first_meaningful_state_ms"], 0),
                    format_decimal(row["first_snapshot_visible_ms"], 0),
                    format_decimal(row["entry_to_queue_visible_ms"], 0),
                    format_decimal(row["event_to_snapshot_visible_ms"], 0),
                    format_decimal(row["sale_to_sales_workspace_visible_ms"], 0),
                    format_decimal(row["snapshot_rate_per_second"], 4),
                    format_decimal(row["entry_rate_per_second"], 4),
                    row["snapshot_count"],
                    row["entry_created_count"],
                ]
                for row in websocket
            ],
            "p{1.8cm}rrrrrrrrr",
        ),
        "## Estabilidade operacional e cobertura diagnóstica",
        render_longtable(
            "Prontidão observada pelos health checks durante as rodadas canônicas.",
            "tab:health-timeline",
            [
                "Backend",
                "Endpoint",
                "Amostras",
                "Não ok",
                "1o ok ms",
                "Transições",
                "Estados observados",
            ],
            [
                [
                    row["backend"],
                    format_cell(row["endpoint"], mode="breakable"),
                    row["sample_count"],
                    row["non_ok_samples"],
                    format_decimal(row["first_ok_ms"], 0),
                    row["transitions"],
                    row["states_seen"],
                ]
                for row in health
            ],
            "L{1.8cm}L{2.4cm}rrrrL{4.6cm}",
        ),
        render_longtable(
            "Cobertura dos snapshots finais de debug nas rodadas canônicas.",
            "tab:debug-snapshots",
            [
                "Backend",
                "Snapshot",
                "OK",
                "Campos",
                "Timestamp",
                "Entries",
                "Balance sheet",
            ],
            [
                [
                    row["backend"],
                    format_cell(row["snapshot"], mode="breakable"),
                    format_decimal(row["ok"]),
                    row["payload_field_count"],
                    format_decimal(row["has_timestamp"]),
                    format_decimal(row["has_entries"]),
                    format_decimal(row["has_balance_sheet"]),
                ]
                for row in debug
            ],
            "L{1.8cm}L{4.0cm}rrrrr",
        ),
        render_longtable(
            "Falhas efetivamente observadas ao longo de todas as rodadas disponíveis.",
            "tab:round-failures",
            [
                "Classe",
                "Backend",
                "Cenário",
                "Round ID",
                "Tipo",
                "Probe",
                "Erros",
                "Amostras",
                "Sucesso",
                "p95 ms",
            ],
            [
                [
                    row["classificacao"],
                    row["backend"],
                    row["cenario"],
                    format_cell(row["round_id"], mode="breakable"),
                    row["probe_type"],
                    format_cell(row["probe_name"], mode="breakable"),
                    row["error_count"],
                    row["sample_count"],
                    row["success_count"],
                    format_decimal(row["p95_ms"]),
                ]
                for row in failures
            ],
            "L{1.8cm}L{1.8cm}L{2.4cm}L{5.6cm}L{1.2cm}L{2.3cm}rrrr",
            landscape=True,
        ),
        "## Recursos computacionais",
        render_longtable(
            "Uso consolidado de recursos computacionais por backend canônico.",
            "tab:resource-totals",
            [
                "Backend",
                "Contêineres",
                "CPU média",
                "CPU pico",
                "Memória média MB",
                "Memória pico MB",
                "Maior contêiner MB",
            ],
            [
                [
                    row["backend"],
                    row["container_count"],
                    format_decimal(row["total_cpu_avg"], 4),
                    format_decimal(row["peak_cpu"], 4),
                    format_decimal(row["total_memory_avg_mb"], 2),
                    format_decimal(row["total_memory_peak_mb"], 2),
                    format_decimal(row["peak_container_memory_mb"], 2),
                ]
                for row in resource_totals
            ],
            "p{1.8cm}rrrrrr",
        ),
        "A tabela consolidada de recursos permanece no corpo principal, mas o detalhamento por contêiner foi repartido por backend para preservar legibilidade sem truncar identificadores nem reduzir excessivamente o corpo tipográfico.",
        "## Síntese orientada pelos dados",
        (
            "As tabelas confirmam que o corpus canônico final preserva corretude contábil total em todos os backends, mas não preserva equivalência operacional entre eles. ClickHouse e Pinot dominam as superfícies HTTP e SQL na maior parte das consultas observadas, enquanto Druid e Materialize exibem custos muito superiores nessas mesmas interfaces."
        ),
        (
            "Ao mesmo tempo, a camada de convergência visual exige leitura menos simplista. Druid mantém `frontend_time_to_first_meaningful_state_ms` muito baixo e cadência de snapshots comparável à de ClickHouse, mesmo com warm-up inicial e erros transitórios na superfície HTTP. Pinot, por contraste, é extremamente competitivo em leitura direta, mas sua cadência autoritativa de snapshots permanece muito inferior nas métricas coletadas."
        ),
        (
            "O inventário histórico das rodadas também mostra por que o artigo não deve se apoiar apenas na última tabela-resumo: houve tentativas substituídas e cenários de validação com falhas concentradas em probes SQL e em fases de readiness. Isso justifica separar explicitamente corpus canônico, corpus auxiliar e evidência diagnóstica, além de orientar futuros reruns de dupla conformação nas trilhas com maior incidência de erro."
        ),
    ]

    resource_sections = render_backend_resource_tables(resource_details)
    synthesis_index = sections.index("## Síntese orientada pelos dados")
    sections[synthesis_index:synthesis_index] = resource_sections

    write_markdown(output_dir / "06-resultados-gerados.md", sections)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())