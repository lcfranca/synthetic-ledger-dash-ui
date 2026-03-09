SHELL := /bin/bash

ENV_FILE ?= .env
STACK_SELECTION := bash scripts/stack-selection.sh
CURL_HEALTH := curl --retry 20 --retry-delay 1 --retry-all-errors -fsS

.PHONY: run stop up down logs ps rebuild populate stop-populate health health-clickhouse health-druid health-pinot health-materialize smoke-clickhouse smoke-druid smoke-pinot smoke-materialize smoke-all smoke-startup print-selection verify-stream-clickhouse verify-stream-druid verify-stream-pinot verify-stream-materialize verify-projection-clickhouse verify-projection-druid verify-projection-pinot verify-projection-materialize

run:
	@if [ ! -f $(ENV_FILE) ]; then cp .env.example $(ENV_FILE); fi
	@services="$$($(STACK_SELECTION) services $(ENV_FILE))"; \
	if [ -z "$$services" ]; then \
		echo "No services resolved from $(ENV_FILE)."; \
		exit 1; \
	fi; \
	eval "$$($(STACK_SELECTION) exports $(ENV_FILE))"; \
	echo "Starting services: $$services"; \
	echo "Resolved stacks: $$ACTIVE_RESOLVED_STACKS"; \
	TARGET_BACKENDS="$$TARGET_BACKENDS" \
	API_ALLOWED_BACKENDS="$$API_ALLOWED_BACKENDS" \
	API_DEFAULT_BACKEND="$$API_DEFAULT_BACKEND" \
	KAFKA_FANOUT_TARGET_BACKENDS="$$KAFKA_FANOUT_TARGET_BACKENDS" \
	docker compose --env-file $(ENV_FILE) up --build -d $$services; \
	$(MAKE) smoke-startup ENV_FILE=$(ENV_FILE)

stop:
	@docker compose --env-file $(ENV_FILE) --profile producer down --remove-orphans --volumes --rmi local --timeout 5 || true
	@project_name="$${COMPOSE_PROJECT_NAME:-$$(basename "$$(pwd)")}"; \
	remaining_containers="$$(docker ps -aq --filter label=com.docker.compose.project=$$project_name)"; \
	if [ -n "$$remaining_containers" ]; then docker rm -f $$remaining_containers >/dev/null 2>&1 || true; fi; \
	remaining_volumes="$$( (docker volume ls -q --filter label=com.docker.compose.project=$$project_name; docker volume ls -q | grep -E "^$${project_name}_") | sort -u )"; \
	if [ -n "$$remaining_volumes" ]; then docker volume rm -f $$remaining_volumes >/dev/null 2>&1 || true; fi; \
	remaining_networks="$$(docker network ls -q --filter label=com.docker.compose.project=$$project_name)"; \
	if [ -n "$$remaining_networks" ]; then docker network rm $$remaining_networks >/dev/null 2>&1 || true; fi; \
	echo "Stack stopped and cleaned."

up:
	@$(MAKE) run ENV_FILE=$(ENV_FILE)

populate:
	@if [ ! -f $(ENV_FILE) ]; then cp .env.example $(ENV_FILE); fi
	@services="$$($(STACK_SELECTION) services $(ENV_FILE))"; \
	eval "$$($(STACK_SELECTION) exports $(ENV_FILE))"; \
	TARGET_BACKENDS="$$TARGET_BACKENDS" \
	API_ALLOWED_BACKENDS="$$API_ALLOWED_BACKENDS" \
	API_DEFAULT_BACKEND="$$API_DEFAULT_BACKEND" \
	KAFKA_FANOUT_TARGET_BACKENDS="$$KAFKA_FANOUT_TARGET_BACKENDS" \
	docker compose --env-file $(ENV_FILE) --profile producer up --build -d $$services producer

stop-populate:
	docker compose --env-file $(ENV_FILE) stop producer

down:
	@$(MAKE) stop ENV_FILE=$(ENV_FILE)

logs:
	docker compose --env-file $(ENV_FILE) logs -f --tail=200

ps:
	docker compose --env-file $(ENV_FILE) ps

rebuild:
	docker compose --env-file $(ENV_FILE) build --no-cache

print-selection:
	@if [ ! -f $(ENV_FILE) ]; then cp .env.example $(ENV_FILE); fi
	@echo "Services: $$($(STACK_SELECTION) services $(ENV_FILE))"
	@$(STACK_SELECTION) exports $(ENV_FILE)

health:
	@echo "Master Data:" && $(CURL_HEALTH) http://localhost:8091/health && echo
	@echo "Kafka UI:" && curl -fsSI http://localhost:8090 | head -n 1
	@echo "Storage Writer:" && $(CURL_HEALTH) http://localhost:8092/health && echo
	@echo "Realtime Gateway:" && $(CURL_HEALTH) http://localhost:8083/health && echo
	@eval "$$($(STACK_SELECTION) exports $(ENV_FILE))"; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)clickhouse($$|,)'; then echo "API ClickHouse:" && $(CURL_HEALTH) http://localhost:8080/health && echo; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)druid($$|,)'; then echo "API Druid:" && $(CURL_HEALTH) http://localhost:8081/health && echo; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)pinot($$|,)'; then echo "API Pinot:" && $(CURL_HEALTH) http://localhost:8082/health && echo; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)materialize($$|,)'; then echo "API Materialize:" && $(CURL_HEALTH) http://localhost:8084/health && echo; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)clickhouse($$|,)'; then echo "Frontend ClickHouse:" && curl -fsSI http://localhost:5173 | head -n 1; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)druid($$|,)'; then echo "Frontend Druid:" && curl -fsSI http://localhost:5174 | head -n 1; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)pinot($$|,)'; then echo "Frontend Pinot:" && curl -fsSI http://localhost:5175 | head -n 1; fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)materialize($$|,)'; then echo "Frontend Materialize:" && curl -fsSI http://localhost:5176 | head -n 1; fi

health-clickhouse:
	@echo "ClickHouse API:" && $(CURL_HEALTH) http://localhost:8080/health && echo
	@echo "ClickHouse Frontend:" && curl -fsSI http://localhost:5173 | head -n 1
	@echo "ClickHouse Realtime Stream:" && node scripts/verify_realtime_stream.mjs clickhouse 5173
	@echo "ClickHouse Realtime Projection:" && node scripts/verify_realtime_projection.mjs clickhouse 5173

health-druid:
	@echo "Druid API:" && $(CURL_HEALTH) http://localhost:8081/health && echo
	@echo "Druid Frontend:" && curl -fsSI http://localhost:5174 | head -n 1
	@echo "Druid Supervisor:" && $(CURL_HEALTH) http://localhost:8092/debug/druid-supervisor && echo
	@echo "Druid Realtime Stream:" && node scripts/verify_realtime_stream.mjs druid 5174
	@echo "Druid Realtime Projection:" && node scripts/verify_realtime_projection.mjs druid 5174

health-pinot:
	@echo "Pinot API:" && $(CURL_HEALTH) http://localhost:8082/health && echo
	@echo "Pinot Frontend:" && curl -fsSI http://localhost:5175 | head -n 1
	@echo "Pinot Realtime:" && $(CURL_HEALTH) http://localhost:8092/debug/pinot-realtime && echo
	@echo "Pinot Realtime Stream:" && node scripts/verify_realtime_stream.mjs pinot 5175
	@echo "Pinot Realtime Projection:" && node scripts/verify_realtime_projection.mjs pinot 5175

health-materialize:
	@echo "Materialize API:" && $(CURL_HEALTH) http://localhost:8084/health && echo
	@echo "Materialize Frontend:" && curl -fsSI http://localhost:5176 | head -n 1
	@echo "Materialize Bootstrap:" && $(CURL_HEALTH) http://localhost:8092/debug/materialize-bootstrap && echo
	@echo "Materialize Realtime Stream:" && node scripts/verify_realtime_stream.mjs materialize 5176
	@echo "Materialize Realtime Projection:" && node scripts/verify_realtime_projection.mjs materialize 5176

smoke-clickhouse:
	@echo "ClickHouse summary:" && curl -fsS http://localhost:8080/api/v1/dashboard/summary | head -c 400 && echo
	@echo "ClickHouse entries:" && curl -fsS 'http://localhost:8080/api/v1/dashboard/entries?limit=5' | head -c 400 && echo

smoke-druid:
	@echo "Druid summary:" && curl -fsS http://localhost:8081/api/v1/dashboard/summary | head -c 400 && echo
	@echo "Druid entries:" && curl -fsS 'http://localhost:8081/api/v1/dashboard/entries?limit=5' | head -c 400 && echo
	@echo "Druid SQL count:" && curl -fsS -X POST http://localhost:8889/druid/v2/sql -H 'Content-Type: application/json' -d '{"query":"SELECT COUNT(*) AS c FROM \"ledger_events\""}' && echo

smoke-pinot:
	@echo "Pinot summary:" && curl -fsS http://localhost:8082/api/v1/dashboard/summary | head -c 400 && echo
	@echo "Pinot entries:" && curl -fsS 'http://localhost:8082/api/v1/dashboard/entries?limit=5' | head -c 400 && echo
	@echo "Pinot SQL count:" && curl -fsS -X POST http://localhost:8099/query/sql -H 'Content-Type: application/json' -d '{"sql":"SELECT COUNT(*) AS c FROM ledger_events"}' && echo

smoke-materialize:
	@echo "Materialize summary:" && curl -fsS http://localhost:8084/api/v1/dashboard/summary | head -c 400 && echo
	@echo "Materialize entries:" && curl -fsS 'http://localhost:8084/api/v1/dashboard/entries?limit=5' | head -c 400 && echo
	@echo "Materialize readiness:" && curl -fsS http://localhost:8084/health | head -c 400 && echo

verify-stream-druid:
	@node scripts/verify_realtime_stream.mjs druid 5174

verify-stream-clickhouse:
	@node scripts/verify_realtime_stream.mjs clickhouse 5173

verify-stream-pinot:
	@node scripts/verify_realtime_stream.mjs pinot 5175

verify-stream-materialize:
	@node scripts/verify_realtime_stream.mjs materialize 5176

verify-projection-clickhouse:
	@node scripts/verify_realtime_projection.mjs clickhouse 5173

verify-projection-druid:
	@node scripts/verify_realtime_projection.mjs druid 5174

verify-projection-pinot:
	@node scripts/verify_realtime_projection.mjs pinot 5175

verify-projection-materialize:
	@node scripts/verify_realtime_projection.mjs materialize 5176

smoke-all:
	@eval "$$($(STACK_SELECTION) exports $(ENV_FILE))"; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)clickhouse($$|,)'; then $(MAKE) smoke-clickhouse ENV_FILE=$(ENV_FILE); fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)druid($$|,)'; then $(MAKE) smoke-druid ENV_FILE=$(ENV_FILE); fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)pinot($$|,)'; then $(MAKE) smoke-pinot ENV_FILE=$(ENV_FILE); fi; \
	if echo "$$ACTIVE_RESOLVED_STACKS" | grep -Eq '(^|,)materialize($$|,)'; then $(MAKE) smoke-materialize ENV_FILE=$(ENV_FILE); fi

smoke-startup:
	@set -a; source $(ENV_FILE); set +a; \
	eval "$$($(STACK_SELECTION) exports $(ENV_FILE))"; \
	ACTIVE_STACKS="$$ACTIVE_RESOLVED_STACKS" RUN_PRODUCER_ON_START="$${RUN_PRODUCER_ON_START:-false}" python3 scripts/smoke_accounting.py
