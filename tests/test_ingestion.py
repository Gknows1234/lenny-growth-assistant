import pytest

from scripts.ingest import archive_url, chunk_transcript, stable_source_id, timestamp_seconds


def test_timestamp_parses_minute_and_hour_forms() -> None:
    assert timestamp_seconds("Guest (03:15): hello") == 195
    assert timestamp_seconds("Guest (01:03:15): hello") == 3_795
    assert timestamp_seconds("no timestamp") is None


def test_chunker_keeps_timestamp_and_boundary_overlap() -> None:
    chunks = chunk_transcript(
        "Guest (00:10): First short point.\n\n"
        "Lenny (00:20): Second short point.\n\n"
        "Guest (00:30): Third short point.",
        target_chars=85,
    )
    assert len(chunks) >= 2
    assert chunks[0][1] == 10
    assert "Second short point" in chunks[0][0]
    assert "Second short point" in chunks[1][0]


def test_archive_url_is_restricted_to_github_and_safe_ref() -> None:
    assert archive_url(
        "https://github.com/ChatPRD/lennys-podcast-transcripts.git", "main"
    ).endswith("/archive/refs/heads/main.tar.gz")
    with pytest.raises(ValueError):
        archive_url("https://example.com/repo.git", "main")
    with pytest.raises(ValueError):
        archive_url("https://github.com/owner/repo.git", "../../secrets")


def test_long_source_ids_are_stable_and_fit_schema() -> None:
    slug = "a-very-long-combined-guest-name-" * 4
    assert stable_source_id(slug) == stable_source_id(slug)
    assert len(stable_source_id(slug)) == 64
