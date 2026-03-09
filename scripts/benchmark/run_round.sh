#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/common.sh"

backend="${1:-}"
scenario="${2:-bootstrap-operational}"
run_number="${3:-1}"
collection_seconds="${4:-270}"
bootstrap_timeout_seconds="${BENCHMARK_BOOTSTRAP_TIMEOUT_SECONDS:-$BENCHMARK_DEFAULT_BOOTSTRAP_TIMEOUT_SECONDS}"
backend_timeout_seconds="${BENCHMARK_BACKEND_TIMEOUT_SECONDS:-$BENCHMARK_DEFAULT_BACKEND_TIMEOUT_SECONDS}"
warmup_seconds="${BENCHMARK_WARMUP_SECONDS:-$BENCHMARK_DEFAULT_WARMUP_SECONDS}"

if [[ -z "$backend" ]]; then
  echo "usage: $0 <backend> [scenario] [run_number] [collection_seconds]" >&2
  exit 1
fi

benchmark_require_backend "$backend"

segment_seconds="$(benchmark_collection_segment_seconds "$collection_seconds")"

output_dir="$(benchmark_create_round_dir "$backend" "$scenario" "$run_number")"
env_file="$output_dir/${backend}.env"
metadata_file="$output_dir/metadata.json"
api_file="$output_dir/api_latencies.json"
sql_file="$output_dir/sql_latencies.json"
ws_file="$output_dir/ws_metrics.json"
resources_file="$output_dir/resources.json"
health_file="$output_dir/health_timeline.json"
debug_file="$output_dir/debug_snapshots.json"

benchmark_prepare_env_file "$backend" "$env_file"
benchmark_write_metadata "$metadata_file" "$backend" "$scenario" "$run_number" "$env_file" "$collection_seconds" "$bootstrap_timeout_seconds" "$backend_timeout_seconds" "$warmup_seconds"

cleanup() {
  make -C "$BENCHMARK_REPO_ROOT" stop ENV_FILE="$env_file" >/dev/null 2>&1 || true
}

benchmark_up_services() {
  local env_file="$1"
  local services
  local exports

  services="$(bash "$BENCHMARK_REPO_ROOT/scripts/stack-selection.sh" services "$env_file")"
  exports="$(bash "$BENCHMARK_REPO_ROOT/scripts/stack-selection.sh" exports "$env_file")"

  if [[ -z "$services" ]]; then
    echo "No services resolved from $env_file" >&2
    exit 1
  fi

  eval "$exports"
  echo "[benchmark] starting services: $services"
  echo "[benchmark] resolved stacks: $ACTIVE_RESOLVED_STACKS"

  TARGET_BACKENDS="$TARGET_BACKENDS" \
  API_ALLOWED_BACKENDS="$API_ALLOWED_BACKENDS" \
  API_DEFAULT_BACKEND="$API_DEFAULT_BACKEND" \
  KAFKA_FANOUT_TARGET_BACKENDS="$KAFKA_FANOUT_TARGET_BACKENDS" \
  docker compose --env-file "$env_file" up --build -d $services
}

trap cleanup EXIT

echo "[benchmark] starting round for $backend -> $output_dir"

make -C "$BENCHMARK_REPO_ROOT" stop ENV_FILE="$env_file" >/dev/null 2>&1 || true
benchmark_up_services "$env_file"
make -C "$BENCHMARK_REPO_ROOT" populate ENV_FILE="$env_file"

benchmark_wait_for_http_ok "http://localhost:8091/health" "$bootstrap_timeout_seconds" "master-data"
benchmark_wait_for_http_ok "http://localhost:8092/health" "$bootstrap_timeout_seconds" "storage-writer"
benchmark_wait_for_http_ok "http://localhost:8083/health" "$bootstrap_timeout_seconds" "realtime-gateway"
benchmark_wait_for_http_ok "$(benchmark_backend_health_url "$backend")" "$backend_timeout_seconds" "backend-api"
benchmark_wait_for_http_ok "$(benchmark_frontend_base_url "$backend")" "$bootstrap_timeout_seconds" "frontend"
benchmark_wait_for_http_ok "$(benchmark_debug_endpoint "$backend")" "$backend_timeout_seconds" "backend-debug"

if [[ "$backend" == "materialize" ]]; then
  benchmark_wait_for_materialize_bootstrap_ready "$backend_timeout_seconds"
fi

benchmark_warmup_requests "$backend"
sleep "$warmup_seconds"

python3 "$SCRIPT_DIR/collect_health_timeline.py" \
  --backend "$backend" \
  --duration-seconds "$collection_seconds" \
  --output "$health_file" \
  > "$output_dir/health_timeline.log" 2>&1 &
health_pid=$!

python3 "$SCRIPT_DIR/collect_container_stats.py" \
  --duration-seconds "$collection_seconds" \
  --output "$resources_file" \
  > "$output_dir/container_stats.log" 2>&1 &
resources_pid=$!

python3 "$SCRIPT_DIR/collect_api_latencies.py" \
  --backend "$backend" \
  --base-url "$(benchmark_backend_base_url "$backend")" \
  --duration-seconds "$segment_seconds" \
  --output "$api_file"

python3 "$SCRIPT_DIR/collect_sql_latencies.py" \
  --backend "$backend" \
  --env-file "$env_file" \
  --duration-seconds "$segment_seconds" \
  --output "$sql_file"

node "$SCRIPT_DIR/collect_ws_convergence.mjs" \
  --backend "$backend" \
  --frontend-port "$(benchmark_frontend_port "$backend")" \
  --duration-seconds "$segment_seconds" \
  --output "$ws_file"

wait "$health_pid"
wait "$resources_pid"

python3 "$SCRIPT_DIR/collect_debug_snapshots.py" \
  --backend "$backend" \
  --output "$debug_file"

python3 "$SCRIPT_DIR/consolidate_round_results.py" \
  --round-dir "$output_dir"

echo "[benchmark] round completed -> $output_dir"