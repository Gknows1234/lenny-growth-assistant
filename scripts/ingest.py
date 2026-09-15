#!/usr/bin/env python
"""Fetch, chunk, and index the public Lenny's Podcast transcript repository."""

import argparse
import asyncio
import hashlib
import logging
import re
import shutil
import tarfile
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import frontmatter
import httpx
from sqlalchemy import delete, func, select

from app.core.config import get_settings
from app.core.logging import configure_logging
from app.db.base import IngestionRun, TranscriptChunk, TranscriptSource
from app.db.session import SessionLocal

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("ingest")
TIMESTAMP_RE = re.compile(r"\((?:(\d{1,2}):)?(\d{1,2}):(\d{2})\)")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, help="Use an existing transcript checkout")
    parser.add_argument(
        "--refresh", action="store_true", help="Re-download and re-index changed files"
    )
    parser.add_argument(
        "--if-empty", action="store_true", help="Exit when the index already has data"
    )
    parser.add_argument("--limit", type=int, default=settings.ingest_limit)
    return parser.parse_args()


def archive_url(repo: str, ref: str) -> str:
    parsed = urlparse(repo)
    if parsed.hostname != "github.com":
        raise ValueError("Automatic download only accepts a github.com repository URL")
    path = parsed.path.removesuffix(".git").strip("/")
    if len(path.split("/")) != 2:
        raise ValueError("Expected a GitHub owner/repository URL")
    if not re.fullmatch(r"[A-Za-z0-9._/-]+", ref) or ".." in ref:
        raise ValueError("Transcript ref contains unsupported characters")
    return f"https://github.com/{path}/archive/refs/heads/{ref}.tar.gz"


def safe_extract(archive: tarfile.TarFile, destination: Path) -> None:
    destination = destination.resolve()
    for member in archive.getmembers():
        target = (destination / member.name).resolve()
        if destination not in target.parents and target != destination:
            raise ValueError("Archive contains an unsafe path")
    archive.extractall(destination, filter="data")


def replace_directory_contents(source: Path, destination: Path) -> None:
    """Replace a checkout without deleting its directory, which may be a volume mount."""
    destination.mkdir(parents=True, exist_ok=True)
    for child in destination.iterdir():
        if child.is_dir() and not child.is_symlink():
            shutil.rmtree(child)
        else:
            child.unlink()
    shutil.copytree(source, destination, dirs_exist_ok=True)


async def download_transcripts(destination: Path, refresh: bool) -> Path:
    episodes = destination / "episodes"
    if episodes.exists() and not refresh:
        return destination

    url = archive_url(settings.transcript_repo, settings.transcript_ref)
    logger.info("transcript_download_started", extra={"url": url})
    with tempfile.TemporaryDirectory() as temporary:
        temporary_path = Path(temporary)
        archive_path = temporary_path / "transcripts.tar.gz"
        async with (
            httpx.AsyncClient(timeout=120, follow_redirects=True) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            with archive_path.open("wb") as handle:
                async for chunk in response.aiter_bytes():
                    handle.write(chunk)
        with tarfile.open(archive_path, "r:gz") as archive:
            safe_extract(archive, temporary_path)
        roots = [path for path in temporary_path.iterdir() if path.is_dir()]
        root = next((path for path in roots if (path / "episodes").exists()), None)
        if root is None:
            raise ValueError("Downloaded repository did not contain an episodes directory")
        replace_directory_contents(root, destination)
    logger.info("transcript_download_completed", extra={"destination": str(destination)})
    return destination


def timestamp_seconds(text: str) -> int | None:
    match = TIMESTAMP_RE.search(text)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours or 0) * 3600 + int(minutes) * 60 + int(seconds)


def chunk_transcript(content: str, target_chars: int = 1_600) -> list[tuple[str, int | None]]:
    paragraphs = [item.strip() for item in re.split(r"\n\s*\n", content) if item.strip()]
    chunks: list[tuple[str, int | None]] = []
    current: list[str] = []
    current_size = 0
    current_time: int | None = None

    for paragraph in paragraphs:
        if current and current_size + len(paragraph) > target_chars:
            chunks.append(("\n\n".join(current), current_time))
            overlap = current[-1:] if len(current[-1]) < 500 else []
            current = overlap.copy()
            current_size = sum(len(item) for item in current)
            current_time = timestamp_seconds(current[0]) if current else None
        if current_time is None:
            current_time = timestamp_seconds(paragraph)
        current.append(paragraph)
        current_size += len(paragraph) + 2
    if current:
        chunks.append(("\n\n".join(current), current_time))
    return chunks


def clean_metadata(metadata: dict[str, object]) -> dict[str, object]:
    return {
        str(key): value.isoformat() if hasattr(value, "isoformat") else value
        for key, value in metadata.items()
        if isinstance(value, str | int | float | bool | type(None)) or hasattr(value, "isoformat")
    }


def stable_source_id(slug: str) -> str:
    if len(slug) <= 64:
        return slug
    suffix = hashlib.sha256(slug.encode()).hexdigest()[:10]
    return f"{slug[:53]}-{suffix}"


async def index_checkout(root: Path, limit: int) -> tuple[int, int]:
    transcript_files = sorted((root / "episodes").glob("*/transcript.md"))
    if not transcript_files:
        raise ValueError(f"No episodes/*/transcript.md files found under {root}")
    if limit:
        transcript_files = transcript_files[:limit]
    sources_seen = 0
    chunks_written = 0

    async with SessionLocal() as db:
        run = IngestionRun(
            status="running",
            source_ref=f"{settings.transcript_repo}@{settings.transcript_ref}",
        )
        db.add(run)
        await db.commit()
        run_id = run.id
        try:
            for path in transcript_files:
                post = frontmatter.load(path)
                body = post.content.strip()
                if not body:
                    continue
                digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
                source_slug = path.parent.name
                source_id = stable_source_id(source_slug)
                existing = await db.get(TranscriptSource, source_id)
                if existing and existing.content_hash == digest:
                    sources_seen += 1
                    continue

                chunks = chunk_transcript(body)
                if existing:
                    await db.execute(
                        delete(TranscriptChunk).where(TranscriptChunk.source_id == source_id)
                    )
                    existing.guest = str(
                        post.metadata.get("guest") or source_slug.replace("-", " ").title()
                    )[:300]
                    existing.title = str(post.metadata.get("title") or existing.guest)[:500]
                    existing.youtube_url = str(post.metadata.get("youtube_url") or "")[:500] or None
                    existing.publish_date = str(post.metadata.get("publish_date") or "") or None
                    existing.source_path = str(path.relative_to(root))
                    existing.content_hash = digest
                    existing.source_metadata = clean_metadata(post.metadata)
                    existing.indexed_at = datetime.now(UTC)
                else:
                    db.add(
                        TranscriptSource(
                            id=source_id,
                            guest=str(
                                post.metadata.get("guest") or source_slug.replace("-", " ").title()
                            )[:300],
                            title=str(
                                post.metadata.get("title") or source_slug.replace("-", " ").title()
                            )[:500],
                            youtube_url=str(post.metadata.get("youtube_url") or "")[:500] or None,
                            publish_date=str(post.metadata.get("publish_date") or "") or None,
                            source_path=str(path.relative_to(root)),
                            content_hash=digest,
                            source_metadata=clean_metadata(post.metadata),
                        )
                    )
                    # No ORM relationship links these rows, so make the FK parent durable
                    # before SQLAlchemy batches the transcript chunk inserts.
                    await db.flush()

                for ordinal, (chunk, start) in enumerate(chunks):
                    chunk_digest = hashlib.sha256(
                        f"{source_id}:{ordinal}:{chunk}".encode()
                    ).hexdigest()[:24]
                    db.add(
                        TranscriptChunk(
                            id=f"{source_id[:45]}-{chunk_digest}",
                            source_id=source_id,
                            ordinal=ordinal,
                            content=chunk,
                            start_seconds=start,
                        )
                    )
                await db.commit()
                sources_seen += 1
                chunks_written += len(chunks)
                logger.info(
                    "transcript_indexed",
                    extra={"source_id": source_id, "chunks": len(chunks)},
                )

            run.status = "completed"
            run.sources_seen = sources_seen
            run.chunks_written = chunks_written
            run.completed_at = datetime.now(UTC)
            await db.commit()
            return sources_seen, chunks_written
        except Exception as exc:
            await db.rollback()
            stored = await db.get(IngestionRun, run_id)
            if stored:
                stored.status = "failed"
                stored.error = str(exc)[:2_000]
                stored.completed_at = datetime.now(UTC)
                await db.commit()
            raise


async def main() -> None:
    args = parse_args()
    if args.if_empty:
        async with SessionLocal() as db:
            count = await db.scalar(select(func.count()).select_from(TranscriptSource))
            if count:
                logger.info("ingestion_skipped_existing_index", extra={"sources": count})
                return
    checkout = args.source or Path("data/transcripts")
    if not args.source:
        checkout = await download_transcripts(checkout, args.refresh)
    sources, chunks = await index_checkout(checkout, args.limit)
    logger.info("ingestion_finished", extra={"sources": sources, "chunks_written": chunks})


if __name__ == "__main__":
    asyncio.run(main())
