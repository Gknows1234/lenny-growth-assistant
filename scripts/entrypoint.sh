#!/bin/sh
set -eu

mkdir -p /workspace/data/transcripts
chown app:app /workspace/data /workspace/data/transcripts

run_as_app() {
  runuser -u app -- "$@"
}

run_as_app alembic upgrade head

if [ "${AUTO_INGEST:-true}" = "true" ]; then
  run_as_app python -m scripts.ingest --if-empty || echo '{"level":"warning","event":"ingest_unavailable","message":"Starting with the existing index; run the documented refresh command when network access is available."}'
fi

exec runuser -u app -- uvicorn app.main:app --host 0.0.0.0 --port 8000
