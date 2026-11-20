"""
Knowledge Brain service — ingestion, chunking, embedding, and management.
"""
from typing import List, Optional
from uuid import UUID
import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update
from app.models.models import KnowledgeSource, KnowledgeChunk, KnowledgeSourceType
from app.ai.gemini_client import get_embedding
from app.utils.text_processing import chunk_text, clean_text
from app.utils.security import validate_public_url
from app.config import get_settings
import logging
import io

logger = logging.getLogger(__name__)
settings = get_settings()


async def ingest_text(
    db: AsyncSession,
    business_id: UUID,
    title: str,
    content: str,
) -> KnowledgeSource:
    """Ingest plain text into the Knowledge Brain."""
    source = KnowledgeSource(
        business_id=business_id,
        source_type=KnowledgeSourceType.text,
        title=title,
        original_content=content,
    )
    db.add(source)
    await db.flush()
    await _process_source(db, source, content)
    await db.commit()
    await db.refresh(source)
    return source


async def ingest_pdf(
    db: AsyncSession,
    business_id: UUID,
    file_bytes: bytes,
    file_name: str,
) -> KnowledgeSource:
    """Extract text from PDF and ingest into the Knowledge Brain."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        text_parts = []
        for page in doc:
            text_parts.append(page.get_text())
        content = "\n\n".join(text_parts)
    except Exception as e:
        logger.error(f"PyMuPDF failed: {e}, trying pdfplumber")
        import pdfplumber
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            content = "\n\n".join(
                page.extract_text() or "" for page in pdf.pages
            )

    content = clean_text(content)

    source = KnowledgeSource(
        business_id=business_id,
        source_type=KnowledgeSourceType.pdf,
        title=file_name,
        file_name=file_name,
        original_content=content,
    )
    db.add(source)
    await db.flush()
    await _process_source(db, source, content)
    await db.commit()
    await db.refresh(source)
    return source


async def ingest_url(
    db: AsyncSession,
    business_id: UUID,
    url: str,
    title: Optional[str] = None,
) -> KnowledgeSource:
    """Scrape a URL and ingest its readable content safely with SSRF protection."""
    url = validate_public_url(url)

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        response = await client.get(url, headers={"User-Agent": "SupportBrainBot/1.0"})
        response.raise_for_status()

    soup = BeautifulSoup(response.text, "lxml")

    # Remove scripts, styles, and nav elements
    for tag in soup(["script", "style", "nav", "header", "footer", "aside", "iframe"]):
        tag.decompose()

    content = soup.get_text(separator="\n")
    content = clean_text(content)

    page_title = title or (soup.title.string.strip() if soup.title else url)

    source = KnowledgeSource(
        business_id=business_id,
        source_type=KnowledgeSourceType.url,
        title=page_title,
        source_url=url,
        original_content=content,
    )
    db.add(source)
    await db.flush()
    await _process_source(db, source, content)
    await db.commit()
    await db.refresh(source)
    return source


async def _process_source(
    db: AsyncSession,
    source: KnowledgeSource,
    content: str,
) -> None:
    """Chunk content, generate embeddings, and store chunks."""
    chunks = chunk_text(content, settings.CHUNK_SIZE, settings.CHUNK_OVERLAP)
    logger.info(f"Processing source {source.id}: {len(chunks)} chunks")

    for idx, chunk_text_content in enumerate(chunks):
        embedding = get_embedding(chunk_text_content, task_type="RETRIEVAL_DOCUMENT")
        chunk = KnowledgeChunk(
            business_id=source.business_id,
            source_id=source.id,
            chunk_index=idx,
            content=chunk_text_content,
            embedding=embedding,
            token_count=len(chunk_text_content.split()),
        )
        db.add(chunk)

    source.is_processed = True
    source.chunk_count = len(chunks)


async def delete_source(
    db: AsyncSession,
    business_id: UUID,
    source_id: UUID,
) -> bool:
    """Delete a knowledge source and all its chunks (business-scoped)."""
    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.business_id == business_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return False
    await db.delete(source)
    await db.commit()
    return True


async def update_chunk(
    db: AsyncSession,
    business_id: UUID,
    chunk_id: UUID,
    new_content: str,
) -> Optional[KnowledgeChunk]:
    """Update a chunk's content and re-embed it."""
    result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.id == chunk_id,
            KnowledgeChunk.business_id == business_id,
        )
    )
    chunk = result.scalar_one_or_none()
    if not chunk:
        return None

    chunk.content = new_content
    chunk.embedding = get_embedding(new_content, task_type="RETRIEVAL_DOCUMENT")
    chunk.token_count = len(new_content.split())
    await db.commit()
    await db.refresh(chunk)
    return chunk


async def reprocess_source(
    db: AsyncSession,
    business_id: UUID,
    source_id: UUID,
) -> Optional[KnowledgeSource]:
    """Delete all existing chunks and reprocess the original content."""
    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.business_id == business_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source or not source.original_content:
        return None

    # Delete existing chunks
    await db.execute(
        delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id)
    )
    source.is_processed = False
    source.chunk_count = 0
    await db.flush()

    await _process_source(db, source, source.original_content)
    await db.commit()
    await db.refresh(source)
    return source


async def update_source(
    db: AsyncSession,
    business_id: UUID,
    source_id: UUID,
    title: Optional[str] = None,
    content: Optional[str] = None,
) -> Optional[KnowledgeSource]:
    """
    Update a knowledge source's title and/or content.
    If content is updated, removes all outdated chunks and re-embeds new chunks.
    Avoids outdated chunks remaining in vector search results.
    """
    result = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.business_id == business_id,
        )
    )
    source = result.scalar_one_or_none()
    if not source:
        return None

    if title is not None:
        source.title = title

    if content is not None:
        cleaned = clean_text(content)
        source.original_content = cleaned

        # Delete all outdated chunks for this source
        await db.execute(
            delete(KnowledgeChunk).where(KnowledgeChunk.source_id == source_id)
        )
        source.is_processed = False
        source.chunk_count = 0
        await db.flush()

        # Re-chunk and re-embed with fresh vectors
        await _process_source(db, source, cleaned)

    await db.commit()
    await db.refresh(source)
    return source
