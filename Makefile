.PHONY: up down logs test lint ingest

up:
	docker compose up --build

down:
	docker compose down

logs:
	docker compose logs -f api db

test:
	docker compose run --rm --no-deps api pytest

lint:
	docker compose run --rm --no-deps api ruff check .

ingest:
	docker compose exec api python scripts/ingest.py --refresh
