#!/bin/sh
set -eu

alembic upgrade head

if [ "${AUTO_INGEST:-true}" = "true" ]; then
  python scripts/ingest.py --if-empty || echo '{"level":"warning","event":"ingest_unavailable","message":"Starting with the existing index; run the documented refresh command when network access is available."}'
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000

