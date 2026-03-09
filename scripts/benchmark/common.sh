#!/usr/bin/env bash

set -euo pipefail

BENCHMARK_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_REPO_ROOT="$(cd "$BENCHMARK_SCRIPT_DIR/../.." && pwd)"
BENCHMARK_ARTIFACT_ROOT="${BENCHMARK_ARTIFACT_ROOT:-$BENCHMARK_REPO_ROOT/artifacts/benchmark}"

BENCHMARK_DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS="${BENCHMARK_DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS:-180}"
BENCHMARK_DEFAULT_BACKEND_TIMEOUT_SECONDS="${BENCHMARK_DEFAULT_BACKEND_TIMEOUT_SECONDS:-240}"
BENCHMARK_DEFAULT_WARMUP_SECONDS="${BENCHMARK_DEFAULT_WARMUP_SECONDS:-10}"
BENCHMARK_MIN_SEGMENT_SECONDS="${BENCHMARK_MIN_SEGMENT_SECONDS:-45}"

mkdir -p "$BENCHMARK_ARTIFACT_ROOT"

benchmark_collection_segment_seconds() {
  local collection_seconds="$1"
  local segment_seconds=$(( collection_seconds / 3 ))
  if (( segment_seconds < BENCHMARK_MIN_SEGMENT_SECONDS )); then
    segment_seconds="$BENCHMARK_MIN_SEGMENT_SECONDS"
  fi
  echo "$segment_seconds"
}

benchmark_require_backend() {
  local backend="$1"
  case "$backend" in
    clickhouse|druid|pinot|materialize) ;;
    *)
      echo "unsupported backend: $backend" >&2
      exit 1
      ;;
  esac
}

benchmark_api_port() {
  case "$1" in
    clickhouse) echo 8080 ;;
    druid) echo 8081 ;;
    pinot) echo 8082 ;;
    materialize) echo 8084 ;;
  esac
}

benchmark_frontend_port() {
  case "$1" in
    clickhouse) echo 5173 ;;
    druid) echo 5174 ;;
    pinot) echo 5175 ;;
    materialize) echo 5176 ;;
  esac
}

benchmark_backend_health_url() {
  local backend="$1"
  echo "http://localhost:$(benchmark_api_port "$backend")/health"
}

benchmark_backend_base_url() {
  local backend="$1"
  echo "http://localhost:$(benchmark_api_port "$backend")"
}

benchmark_frontend_base_url() {
  local backend="$1"
  echo "http://localhost:$(benchmark_frontend_port "$backend")"
}

benchmark_debug_endpoint() {
  case "$1" in
    clickhouse) echo "http://localhost:8092/debug/kafka-fanout" ;;
    druid) echo "http://localhost:8092/debug/druid-supervisor" ;;
    pinot) echo "http://localhost:8092/debug/pinot-realtime" ;;
    materialize) echo "http://localhost:8092/debug/materialize-bootstrap" ;;
  esac
}

benchmark_create_round_dir() {
  local backend="$1"
  local scenario="$2"
  local run_number="$3"
  local timestamp
  timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local round_id="${timestamp}__${backend}__${scenario}__run-${run_number}"
  local output_dir="$BENCHMARK_ARTIFACT_ROOT/$round_id"
  mkdir -p "$output_dir"
  echo "$output_dir"
}

benchmark_prepare_env_file() {
  local backend="$1"
  local destination="$2"

  cp "$BENCHMARK_REPO_ROOT/.env.example" "$destination"
  sed -i "s/^ACTIVE_STACKS=.*/ACTIVE_STACKS=${backend}/" "$destination"
  sed -i "s/^RUN_PRODUCER_ON_START=.*/RUN_PRODUCER_ON_START=false/" "$destination"
  if ! grep -q '^ACTIVE_STACKS=' "$destination"; then
    echo "ACTIVE_STACKS=${backend}" >> "$destination"
  fi
  if ! grep -q '^RUN_PRODUCER_ON_START=' "$destination"; then
    echo 'RUN_PRODUCER_ON_START=false' >> "$destination"
  fi
}

benchmark_wait_for_http_ok() {
  local url="$1"
  local timeout_seconds="$2"
  local label="$3"
  local started_at
  started_at="$(date +%s)"

  while true; do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_seconds )); then
      echo "timeout waiting for ${label} at ${url}" >&2
      return 1
    fi
    sleep 2
  done
}

benchmark_warmup_requests() {
  local backend="$1"
  local base_url
  base_url="$(benchmark_backend_base_url "$backend")"

  curl -fsS "$base_url/health" >/dev/null || true
  curl -fsS "$base_url/api/v1/dashboard/summary" >/dev/null || true
  curl -fsS "$base_url/api/v1/dashboard/workspace" >/dev/null || true
  curl -fsS "$(benchmark_frontend_base_url "$backend")" >/dev/null || true
}

benchmark_wait_for_materialize_bootstrap_ready() {
  local timeout_seconds="$1"
  local started_at
  started_at="$(date +%s)"

  while true; do
    local payload
    payload="$(curl -fsS "http://localhost:8092/debug/materialize-bootstrap" 2>/dev/null || true)"
    if [[ -n "$payload" ]] && echo "$payload" | grep -Eq '"state":"(ready|warming_up|degraded)"'; then
      return 0
    fi
    if (( $(date +%s) - started_at >= timeout_seconds )); then
      echo "timeout waiting for materialize bootstrap to leave bootstrapping state" >&2
      return 1
    fi
    sleep 2
  done
}

benchmark_write_metadata() {
  local output_path="$1"
  local backend="$2"
  local scenario="$3"
  local run_number="$4"
  local env_file="$5"
  local collection_seconds="$6"
  local bootstrap_timeout_seconds="$7"
  local backend_timeout_seconds="$8"
  local warmup_seconds="$9"
  local round_id
  round_id="$(basename "$(dirname "$output_path")")"
  local segment_seconds
  segment_seconds="$(benchmark_collection_segment_seconds "$collection_seconds")"

  cat > "$output_path" <<EOF
{
  "round_id": "${round_id}",
  "commit": "$(git -C "$BENCHMARK_REPO_ROOT" rev-parse HEAD)",
  "branch": "$(git -C "$BENCHMARK_REPO_ROOT" branch --show-current)",
  "backend": "${backend}",
  "scenario": "${scenario}",
  "run_number": ${run_number},
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)",
  "duration_seconds": ${collection_seconds},
  "phase_budget_seconds": {
    "bootstrap_wait": ${bootstrap_timeout_seconds},
    "backend_readiness_wait": ${backend_timeout_seconds},
    "warmup": ${warmup_seconds},
    "per_probe_segment": ${segment_seconds}
  },
  "env_file": "${env_file}",
  "active_stacks": "${backend}",
  "frontend_base_url": "$(benchmark_frontend_base_url "$backend")",
  "api_base_url": "$(benchmark_backend_base_url "$backend")",
  "host_profile": {
    "hostname": "$(hostname)",
    "kernel": "$(uname -srmo)"
  }
}
EOF
}