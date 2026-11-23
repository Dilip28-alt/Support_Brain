"""
Pydantic schemas for Lessons and Pending Questions.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime


# ─────── Lessons ───────

class LessonCreate(BaseModel):
    question: str = Field(..., min_length=5)
    original_answer: Optional[str] = None
    corrected_answer: str = Field(..., min_length=5)
    owner_comment: Optional[str] = None


class LessonUpdate(BaseModel):
    corrected_answer: Optional[str] = None
    owner_comment: Optional[str] = None
    is_active: Optional[bool] = None


class LessonResponse(BaseModel):
    id: UUID
    business_id: UUID
    question: str
    original_answer: Optional[str]
    corrected_answer: str
    owner_comment: Optional[str]
    is_active: bool
    usage_count: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ─────── Pending Questions ───────

class PendingQuestionResponse(BaseModel):
    id: UUID
    business_id: UUID
    source: str
    customer_question: str
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    status: str
    owner_answer: Optional[str] = None
    conversation_id: Optional[UUID] = None
    email_message_id: Optional[UUID] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PendingQuestionResolve(BaseModel):
    owner_answer: str = Field(..., min_length=5)
    add_to_brain: bool = False   # one-click "add to knowledge brain"
    send_via_channel: bool = True


# ─────── Analytics ───────

class WeeklyStats(BaseModel):
    week_start: str
    total_questions: int
    ai_answered: int
    owner_answered: int = 0
    good_answers: int
    bad_answers: int
    pending: int
    lessons_created: int
    lessons_used: int


class AnalyticsSummary(BaseModel):
    total_questions: int
    total_ai_answers: int
    total_owner_answers: int = 0
    good_answers: int
    bad_answers: int
    pending_questions: int
    lessons_created: int
    lessons_used: int
    weekly_trends: List[WeeklyStats]
