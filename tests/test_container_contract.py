from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_container_entrypoint_runs_ingestion_as_module() -> None:
    entrypoint = (ROOT / "scripts" / "entrypoint.sh").read_text(encoding="utf-8")

    assert "python -m scripts.ingest --if-empty" in entrypoint


def test_docker_build_installs_the_application_package() -> None:
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    install_position = dockerfile.index('RUN pip install --upgrade pip && pip install ".[dev]"')

    assert dockerfile.index("COPY app ./app") < install_position
    assert dockerfile.index("COPY scripts ./scripts") < install_position
