"""
Pydantic schemas for Chat, Conversations, and Messages.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.models import MessageRole


class ChatRequest(BaseModel):
    business_slug: Optional[str] = None
    business_token: Optional[str] = None
    question: str = Field(..., min_length=1, max_length=2000)
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    conversation_id: Optional[UUID] = None


class PublicBusinessInfo(BaseModel):
    name: str
    slug: str
    widget_token: str
    description: Optional[str] = None


class SourceChunk(BaseModel):
    chunk_id: UUID
    source_title: Optional[str]
    content: str
    similarity: float


class ChatResponse(BaseModel):
    conversation_id: UUID
    message_id: UUID
    answer: str
    source_chunks: List[SourceChunk]
    lesson_used: Optional[UUID]
    confidence_score: Optional[float]
    is_pending: bool


class MessageResponse(BaseModel):
    id: UUID
    role: MessageRole
    content: str
    source_chunks: Optional[str]   # JSON string
    created_at: datetime

    class Config:
        from_attributes = True


class ConversationResponse(BaseModel):
    id: UUID
    business_id: UUID
    customer_name: Optional[str]
    customer_email: Optional[str]
    is_resolved: bool
    created_at: datetime
    message_count: Optional[int] = 0

    class Config:
        from_attributes = True


class FeedbackCreate(BaseModel):
    message_id: UUID
    conversation_id: UUID
    feedback_type: str   # "good" | "bad"
    question: Optional[str] = None
    ai_answer: Optional[str] = None
    correct_answer: Optional[str] = None
    owner_comment: Optional[str] = None


class AskAgainRequest(BaseModel):
    message_id: Optional[UUID] = None
    conversation_id: Optional[UUID] = None
    question: Optional[str] = None


class AskAgainResponse(BaseModel):
    original_question: str
    previous_answer: str
    new_answer: str
    lesson_used: Optional[UUID]
    knowledge_source_used: Optional[str]
    lesson_retrieved: bool
