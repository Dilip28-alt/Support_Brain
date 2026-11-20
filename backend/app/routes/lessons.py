"""
Lessons routes — CRUD and analytics.
"""
from typing import List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import User, Lesson
from app.schemas.lessons import LessonCreate, LessonUpdate, LessonResponse
from app.ai.gemini_client import get_embedding
from app.utils.auth import get_current_active_user

router = APIRouter(prefix="/api/lessons", tags=["lessons"])


@router.get("/", response_model=List[LessonResponse])
async def list_lessons(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Lesson)
        .where(Lesson.business_id == current_user.business_id)
        .order_by(Lesson.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=LessonResponse, status_code=201)
async def create_lesson(
    data: LessonCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    embedding = get_embedding(data.question, task_type="RETRIEVAL_DOCUMENT")
    lesson = Lesson(
        business_id=current_user.business_id,
        question=data.question,
        original_answer=data.original_answer,
        corrected_answer=data.corrected_answer,
        owner_comment=data.owner_comment,
        embedding=embedding,
        is_active=True,
    )
    db.add(lesson)
    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.patch("/{lesson_id}", response_model=LessonResponse)
async def update_lesson(
    lesson_id: UUID,
    data: LessonUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Lesson).where(
            Lesson.id == lesson_id,
            Lesson.business_id == current_user.business_id,
        )
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, "Lesson not found")

    if data.corrected_answer is not None:
        lesson.corrected_answer = data.corrected_answer
        # Re-embed if answer changes
        lesson.embedding = get_embedding(lesson.question, task_type="RETRIEVAL_DOCUMENT")
    if data.owner_comment is not None:
        lesson.owner_comment = data.owner_comment
    if data.is_active is not None:
        lesson.is_active = data.is_active

    await db.commit()
    await db.refresh(lesson)
    return lesson


@router.delete("/{lesson_id}", status_code=204)
async def delete_lesson(
    lesson_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(Lesson).where(
            Lesson.id == lesson_id,
            Lesson.business_id == current_user.business_id,
        )
    )
    lesson = result.scalar_one_or_none()
    if not lesson:
        raise HTTPException(404, "Lesson not found")
    await db.delete(lesson)
    await db.commit()
