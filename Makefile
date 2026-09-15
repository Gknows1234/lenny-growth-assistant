.PHONY: up down logs test lint ingest

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api db

test:
	docker build --target test -t lenny-growth-assistant-test .
	docker run --rm lenny-growth-assistant-test pytest

lint:
	docker build --target test -t lenny-growth-assistant-test .
	docker run --rm lenny-growth-assistant-test ruff check app scripts tests

ingest:
	docker compose exec api python -m scripts.ingest --refresh
