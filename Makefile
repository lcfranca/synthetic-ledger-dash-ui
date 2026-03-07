SHELL := /bin/bash

.PHONY: up down logs ps rebuild populate stop-populate health health-clickhouse health-druid health-pinot smoke-clickhouse smoke-druid smoke-pinot smoke-all

up:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose up --build -d

populate:
	@if [ ! -f .env ]; then cp .env.example .env; fi
	docker compose --profile producer up --build -d producer

stop-populate:
	docker compose stop producer

down:
	docker compose --profile producer down --remove-orphans

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

rebuild:
	docker compose build --no-cache

health:
	@echo "API:" && curl -fsS http://localhost:8080/health && echo
	@echo "API Druid:" && curl -fsS http://localhost:8081/health && echo
	@echo "API Pinot:" && curl -fsS http://localhost:8082/health && echo
	@echo "Storage Writer:" && curl -fsS http://localhost:8090/health && echo
	@echo "Frontend:" && curl -fsSI http://localhost:5173 | head -n 1
	@echo "Frontend Druid:" && curl -fsSI http://localhost:5174 | head -n 1
	@echo "Frontend Pinot:" && curl -fsSI http://localhost:5175 | head -n 1

health-clickhouse:
	@echo "ClickHouse API:" && curl -fsS http://localhost:8080/health && echo
	@echo "ClickHouse Frontend:" && curl -fsSI http://localhost:5173 | head -n 1

health-druid:
	@echo "Druid API:" && curl -fsS http://localhost:8081/health && echo
	@echo "Druid Frontend:" && curl -fsSI http://localhost:5174 | head -n 1
	@echo "Druid Supervisor:" && curl -fsS http://localhost:8090/debug/druid-supervisor && echo

health-pinot:
	@echo "Pinot API:" && curl -fsS http://localhost:8082/health && echo
	@echo "Pinot Frontend:" && curl -fsSI http://localhost:5175 | head -n 1
	@echo "Pinot Realtime:" && curl -fsS http://localhost:8090/debug/pinot-realtime && echo

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

smoke-all: smoke-clickhouse smoke-druid smoke-pinot
