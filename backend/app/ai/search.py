"""
Semantic search — retrieve relevant knowledge chunks and lessons using pgvector.
All searches are strictly filtered by business_id.
"""
from typing import List, Tuple, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, select
from app.models.models import KnowledgeChunk, KnowledgeSource, Lesson
from app.ai.gemini_client import get_embedding, EMBEDDING_DIM
from app.config import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()


async def search_knowledge(
    db: AsyncSession,
    business_id: UUID,
    query: str,
    top_k: int = None,
    threshold: float = None,
) -> List[dict]:
    """
    Semantic search over knowledge_chunks for a specific business.
    Returns chunks sorted by cosine similarity (highest first).
    """
    top_k = top_k or settings.TOP_K_CHUNKS
    threshold = threshold or settings.SIMILARITY_THRESHOLD

    query_embedding = get_embedding(query, task_type="RETRIEVAL_QUERY")
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT
            kc.id,
            kc.source_id,
            kc.content,
            ks.title AS source_title,
            1 - (kc.embedding <=> :embedding ::vector) AS similarity
        FROM knowledge_chunks kc
        JOIN knowledge_sources ks ON kc.source_id = ks.id
        WHERE kc.business_id = :business_id
          AND kc.embedding IS NOT NULL
          AND 1 - (kc.embedding <=> :embedding ::vector) >= :threshold
        ORDER BY kc.embedding <=> :embedding ::vector
        LIMIT :top_k
    """)

    result = await db.execute(sql, {
        "embedding": embedding_str,
        "business_id": str(business_id),
        "threshold": threshold,
        "top_k": top_k,
    })
    rows = result.fetchall()

    return [
        {
            "chunk_id": row.id,
            "source_id": row.source_id,
            "content": row.content,
            "source_title": row.source_title,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]


async def search_lessons(
    db: AsyncSession,
    business_id: UUID,
    query: str,
    top_k: int = 3,
    threshold: float = 0.45,   # lessons confidence cutoff
) -> List[dict]:
    """
    Semantic search over active lessons for a specific business.
    Lessons are always checked before knowledge chunks.
    """
    query_embedding = get_embedding(query, task_type="RETRIEVAL_QUERY")
    embedding_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

    sql = text("""
        SELECT
            l.id,
            l.question,
            l.corrected_answer,
            l.original_answer,
            l.owner_comment,
            1 - (l.embedding <=> :embedding ::vector) AS similarity
        FROM lessons l
        WHERE l.business_id = :business_id
          AND l.is_active = true
          AND l.embedding IS NOT NULL
          AND 1 - (l.embedding <=> :embedding ::vector) >= :threshold
        ORDER BY l.embedding <=> :embedding ::vector
        LIMIT :top_k
    """)

    result = await db.execute(sql, {
        "embedding": embedding_str,
        "business_id": str(business_id),
        "threshold": threshold,
        "top_k": top_k,
    })
    rows = result.fetchall()

    return [
        {
            "lesson_id": row.id,
            "id": row.id,
            "question": row.question,
            "corrected_answer": row.corrected_answer,
            "original_answer": row.original_answer,
            "similarity": float(row.similarity),
        }
        for row in rows
    ]
