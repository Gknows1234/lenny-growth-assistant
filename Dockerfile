FROM python:3.12-slim AS dependencies

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /workspace

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml ./
RUN pip install --upgrade pip && python -c "import subprocess, sys, tomllib; project = tomllib.load(open('pyproject.toml', 'rb')); subprocess.check_call([sys.executable, '-m', 'pip', 'install', *project['project']['dependencies']])"

FROM dependencies AS test
ENV PYTHONPATH=/workspace
RUN python -c "import subprocess, sys, tomllib; project = tomllib.load(open('pyproject.toml', 'rb')); subprocess.check_call([sys.executable, '-m', 'pip', 'install', *project['project']['optional-dependencies']['dev']])"
COPY app ./app
COPY scripts ./scripts
COPY tests ./tests
COPY Dockerfile .dockerignore ./
COPY alembic.ini ./
COPY alembic ./alembic
CMD ["pytest"]

FROM dependencies AS runtime
ENV PYTHONPATH=/workspace
COPY app ./app
COPY scripts ./scripts
COPY alembic.ini ./
COPY alembic ./alembic
RUN chmod +x scripts/entrypoint.sh && chown -R app:app /workspace

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health/live')"

ENTRYPOINT ["./scripts/entrypoint.sh"]
