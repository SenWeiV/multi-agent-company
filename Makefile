COMPOSE ?= docker compose

.PHONY: up down logs test shell config feishu-long-conn openclaw-sync openclaw-logs

up:
	$(COMPOSE) up --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f app-dev

test:
	$(COMPOSE) run --rm app-dev pytest

shell:
	$(COMPOSE) run --rm app-dev bash

config:
	$(COMPOSE) config

feishu-long-conn:
	$(COMPOSE) run --rm app-dev python -m app.feishu.long_connection

openclaw-sync:
	$(COMPOSE) run --rm openclaw-provisioner

openclaw-logs:
	$(COMPOSE) logs -f openclaw-gateway
