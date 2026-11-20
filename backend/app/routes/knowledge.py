"""
Knowledge Brain routes.
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User, KnowledgeSource, KnowledgeChunk
from app.schemas.knowledge import (
    KnowledgeTextCreate, KnowledgeUrlCreate, KnowledgeSourceResponse,
    KnowledgeChunkResponse, KnowledgeChunkUpdate, KnowledgeSourceUpdate
)
from app.services.knowledge_service import (
    ingest_text, ingest_pdf, ingest_url,
    delete_source, update_chunk, reprocess_source, update_source
)
from app.utils.auth import get_current_active_user
from app.config import get_settings

router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
settings = get_settings()

MAX_BYTES = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


@router.post("/text", response_model=KnowledgeSourceResponse, status_code=201)
async def add_text(
    data: KnowledgeTextCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        source = await ingest_text(db, current_user.business_id, data.title, data.content)
        return source
    except Exception as e:
        import logging
        logging.getLogger("support_brain").error(f"Error in add_text: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to ingest text: {str(e)}")


@router.post("/pdf", response_model=KnowledgeSourceResponse, status_code=201)
async def upload_pdf(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Only PDF files are accepted")

    file_bytes = await file.read()
    if len(file_bytes) > MAX_BYTES:
        raise HTTPException(413, f"File exceeds {settings.MAX_UPLOAD_SIZE_MB}MB limit")
    if len(file_bytes) == 0:
        raise HTTPException(400, "Empty file")

    try:
        source = await ingest_pdf(db, current_user.business_id, file_bytes, file.filename)
        return source
    except Exception as e:
        import logging
        logging.getLogger("support_brain").error(f"Error in upload_pdf: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to ingest PDF: {str(e)}")


@router.post("/url", response_model=KnowledgeSourceResponse, status_code=201)
async def add_url(
    data: KnowledgeUrlCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    try:
        source = await ingest_url(db, current_user.business_id, data.url, data.title)
    except Exception as e:
        raise HTTPException(422, f"Failed to fetch URL: {str(e)}")
    return source


@router.get("/sources", response_model=List[KnowledgeSourceResponse])
async def list_sources(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(KnowledgeSource)
        .where(KnowledgeSource.business_id == current_user.business_id)
        .order_by(KnowledgeSource.created_at.desc())
    )
    return result.scalars().all()


@router.get("/sources/{source_id}/chunks", response_model=List[KnowledgeChunkResponse])
async def list_chunks(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify ownership
    src = await db.execute(
        select(KnowledgeSource).where(
            KnowledgeSource.id == source_id,
            KnowledgeSource.business_id == current_user.business_id,
        )
    )
    if not src.scalar_one_or_none():
        raise HTTPException(404, "Knowledge source not found")

    result = await db.execute(
        select(KnowledgeChunk)
        .where(KnowledgeChunk.source_id == source_id)
        .order_by(KnowledgeChunk.chunk_index)
    )
    return result.scalars().all()


@router.patch("/chunks/{chunk_id}", response_model=KnowledgeChunkResponse)
async def edit_chunk(
    chunk_id: UUID,
    data: KnowledgeChunkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    chunk = await update_chunk(db, current_user.business_id, chunk_id, data.content)
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    return chunk


@router.delete("/chunks/{chunk_id}", status_code=204)
async def delete_chunk(
    chunk_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(KnowledgeChunk).where(
            KnowledgeChunk.id == chunk_id,
            KnowledgeChunk.business_id == current_user.business_id,
        )
    )
    chunk = result.scalar_one_or_none()
    if not chunk:
        raise HTTPException(404, "Chunk not found")
    await db.delete(chunk)
    await db.commit()


@router.delete("/sources/{source_id}", status_code=204)
async def remove_source(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    deleted = await delete_source(db, current_user.business_id, source_id)
    if not deleted:
        raise HTTPException(404, "Knowledge source not found")


@router.post("/sources/{source_id}/reprocess", response_model=KnowledgeSourceResponse)
async def reprocess(
    source_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    source = await reprocess_source(db, current_user.business_id, source_id)
    if not source:
        raise HTTPException(404, "Knowledge source not found or has no content to reprocess")
    return source


@router.patch("/sources/{source_id}", response_model=KnowledgeSourceResponse)
async def modify_source(
    source_id: UUID,
    data: KnowledgeSourceUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Update source title or content (re-chunks and re-embeds to keep search results fresh)."""
    source = await update_source(
        db=db,
        business_id=current_user.business_id,
        source_id=source_id,
        title=data.title,
        content=data.content,
    )
    if not source:
        raise HTTPException(404, "Knowledge source not found")
    return source
