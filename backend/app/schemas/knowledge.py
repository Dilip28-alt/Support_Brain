"""
Pydantic schemas for Knowledge Brain.
"""
from pydantic import BaseModel, HttpUrl, Field, validator
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.models import KnowledgeSourceType


class KnowledgeTextCreate(BaseModel):
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=10)


class KnowledgeUrlCreate(BaseModel):
    url: str = Field(..., description="Website URL to scrape")
    title: Optional[str] = None


class KnowledgeSourceResponse(BaseModel):
    id: UUID
    business_id: UUID
    source_type: KnowledgeSourceType
    title: Optional[str]
    source_url: Optional[str]
    file_name: Optional[str]
    is_processed: bool
    chunk_count: int
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeChunkResponse(BaseModel):
    id: UUID
    source_id: UUID
    chunk_index: int
    content: str
    token_count: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class KnowledgeChunkUpdate(BaseModel):
    content: str = Field(..., min_length=10)


class KnowledgeSourceUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=1, max_length=500)
    content: Optional[str] = Field(None, min_length=10)


class SemanticSearchResult(BaseModel):
    chunk_id: UUID
    source_id: UUID
    source_title: Optional[str]
    content: str
    similarity: float
