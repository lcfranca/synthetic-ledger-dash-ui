#!/usr/bin/env bash

set -euo pipefail

ENV_FILE="${2:-.env}"
MODE="${1:-services}"

if [[ -f "$ENV_FILE" ]]; then
	set -a
	# shellcheck disable=SC1090
	source "$ENV_FILE"
	set +a
fi

ACTIVE_STACKS="${ACTIVE_STACKS:-}"
ENABLE_OTEL_COLLECTOR="${ENABLE_OTEL_COLLECTOR:-true}"
RUN_PRODUCER_ON_START="${RUN_PRODUCER_ON_START:-false}"

declare -A stack_set=()
declare -A service_set=()

trim() {
	local value="$1"
	value="${value#${value%%[![:space:]]*}}"
	value="${value%${value##*[![:space:]]}}"
	printf '%s' "$value"
}

validate_name() {
	case "$1" in
		clickhouse|druid|pinot|materialize)
			return 0
			;;
		*)
			echo "Invalid stack selector '$1'. Use clickhouse, druid, pinot or materialize." >&2
			exit 1
			;;
	esac
}

add_csv_items() {
	local csv_value="$1"
	local raw_items=()
	IFS=',' read -r -a raw_items <<< "$csv_value"
	for raw_item in "${raw_items[@]}"; do
		local item
		item="$(trim "$raw_item")"
		item="${item,,}"
		[[ -z "$item" ]] && continue
		validate_name "$item"
		stack_set["$item"]=1
	done
}

if [[ -z "$ACTIVE_STACKS" ]]; then
	legacy_items=()
	for legacy_value in "${ACTIVE_BACKENDS:-}" "${ACTIVE_APIS:-}" "${ACTIVE_FRONTENDS:-}"; do
		if [[ -n "$legacy_value" ]]; then
			legacy_items+=("$legacy_value")
		fi
	done
	if [[ ${#legacy_items[@]} -gt 0 ]]; then
		ACTIVE_STACKS="$(IFS=,; echo "${legacy_items[*]}")"
	else
		ACTIVE_STACKS="pinot"
	fi
fi

add_csv_items "$ACTIVE_STACKS"

if [[ ${#stack_set[@]} -eq 0 ]]; then
	echo "No active stacks configured. Set ACTIVE_STACKS in $ENV_FILE." >&2
	exit 1
fi

ordered_backends=(clickhouse druid pinot materialize)
stack_list=()

for backend in "${ordered_backends[@]}"; do
	if [[ -v "stack_set[$backend]" ]]; then
		stack_list+=("$backend")
	fi
done

join_by_comma() {
	local items=("$@")
	local joined=""
	local item
	for item in "${items[@]}"; do
		if [[ -z "$joined" ]]; then
			joined="$item"
		else
			joined="$joined,$item"
		fi
	done
	printf '%s' "$joined"
}

default_backend="${stack_list[0]}"
fanout_targets=()
if [[ -v "stack_set[clickhouse]" ]]; then
	fanout_targets+=(clickhouse)
fi

service_set[zookeeper]=1
service_set[kafka]=1
service_set[kafka-ui]=1
service_set[master-data]=1
service_set[storage-writer]=1
service_set[realtime-gateway]=1

if [[ "${ENABLE_OTEL_COLLECTOR,,}" == "true" ]]; then
	service_set[otel-collector]=1
fi

if [[ -v "stack_set[clickhouse]" ]]; then
	service_set[clickhouse]=1
	service_set[api]=1
	service_set[frontend]=1
fi

if [[ -v "stack_set[druid]" ]]; then
	service_set[druid-postgres]=1
	service_set[druid-coordinator]=1
	service_set[druid-overlord]=1
	service_set[druid-broker]=1
	service_set[druid-historical]=1
	service_set[druid-middlemanager]=1
	service_set[druid-router]=1
	service_set[api-druid]=1
	service_set[frontend-druid]=1
fi

if [[ -v "stack_set[pinot]" ]]; then
	service_set[pinot-zookeeper]=1
	service_set[pinot-controller]=1
	service_set[pinot-broker]=1
	service_set[pinot-server]=1
	service_set[api-pinot]=1
	service_set[frontend-pinot]=1
fi

if [[ -v "stack_set[materialize]" ]]; then
	service_set[materialized]=1
	service_set[api-materialize]=1
	service_set[frontend-materialize]=1
fi

if [[ "${RUN_PRODUCER_ON_START,,}" == "true" ]]; then
	service_set[producer]=1
fi

ordered_services=(
	zookeeper
	kafka
	kafka-ui
	clickhouse
	druid-postgres
	druid-coordinator
	druid-overlord
	druid-broker
	druid-historical
	druid-middlemanager
	druid-router
	pinot-zookeeper
	pinot-controller
	pinot-broker
	pinot-server
	materialized
	master-data
	storage-writer
	realtime-gateway
	otel-collector
	api
	api-druid
	api-pinot
	api-materialize
	frontend
	frontend-druid
	frontend-pinot
	frontend-materialize
	producer
)

case "$MODE" in
	services)
		selected_services=()
		for service in "${ordered_services[@]}"; do
				if [[ -v "service_set[$service]" ]]; then
				selected_services+=("$service")
			fi
		done
		printf '%s\n' "${selected_services[*]}"
		;;
	exports)
		printf 'ACTIVE_RESOLVED_STACKS=%q\n' "$(join_by_comma "${stack_list[@]}")"
		printf 'TARGET_BACKENDS=%q\n' "$(join_by_comma "${stack_list[@]}")"
		printf 'API_ALLOWED_BACKENDS=%q\n' "$(join_by_comma "${stack_list[@]}")"
		printf 'API_DEFAULT_BACKEND=%q\n' "$default_backend"
		printf 'KAFKA_FANOUT_TARGET_BACKENDS=%q\n' "$(join_by_comma "${fanout_targets[@]}")"
		;;
	*)
		echo "Unknown mode '$MODE'. Use services or exports." >&2
		exit 1
		;;
esac