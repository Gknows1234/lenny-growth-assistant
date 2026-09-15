from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_container_entrypoint_runs_ingestion_as_module() -> None:
    entrypoint = (ROOT / "scripts" / "entrypoint.sh").read_text(encoding="utf-8")

    assert "run_as_app python -m scripts.ingest --if-empty" in entrypoint
    assert "chown app:app /workspace/data /workspace/data/transcripts" in entrypoint
    assert "exec runuser -u app -- uvicorn" in entrypoint


def test_docker_build_caches_runtime_dependencies_before_source() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    dependency_position = dockerfile.index("project['project']['dependencies']")

    assert dockerfile.index("COPY pyproject.toml ./") < dependency_position
    assert dependency_position < dockerfile.index("COPY app ./app")
    assert dependency_position < dockerfile.index("COPY scripts ./scripts")
    assert "FROM dependencies AS test" in dockerfile
    assert "FROM dependencies AS runtime" in dockerfile
    assert "project['project']['optional-dependencies']['dev']" in dockerfile
    assert "COPY alembic ./alembic" in dockerfile
    assert 'pip install ".[dev]"' not in dockerfile
    assert "COPY . ." not in dockerfile
    assert "USER app" not in dockerfile


def test_docker_context_excludes_local_runtime_and_tools() -> None:
    ignored = (ROOT / ".dockerignore").read_text(encoding="utf-8").splitlines()

    assert ".runtime" in ignored
    assert ".tools" in ignored
    assert ".env" in ignored
