SHELL := /bin/bash

.PHONY: up down logs ps rebuild populate stop-populate health

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
	@echo "Storage Writer:" && curl -fsS http://localhost:8090/health && echo
	@echo "Frontend:" && curl -fsSI http://localhost:5173 | head -n 1
