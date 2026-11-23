"""
Pending Questions routes.
"""
from typing import List
from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import (
    User, PendingQuestion, PendingQuestionStatus,
    Conversation, Message, MessageRole, EmailMessage,
    KnowledgeSource
)
from app.schemas.lessons import PendingQuestionResponse, PendingQuestionResolve
from app.services.knowledge_service import ingest_text
from app.utils.auth import get_current_active_user
from app.email.gmail_service import send_email_reply

router = APIRouter(prefix="/api/pending", tags=["pending-questions"])


@router.get("/", response_model=List[PendingQuestionResponse])
async def list_pending(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    status_filter: str = "open",
):
    query = select(PendingQuestion).where(
        PendingQuestion.business_id == current_user.business_id
    ).order_by(PendingQuestion.created_at.desc())

    if status_filter and status_filter.lower() != "all":
        try:
            query = query.where(PendingQuestion.status == PendingQuestionStatus(status_filter))
        except ValueError:
            pass

    result = await db.execute(query)
    return result.scalars().all()


@router.post("/{question_id}/resolve", response_model=PendingQuestionResponse)
async def resolve_question(
    question_id: UUID,
    data: PendingQuestionResolve,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(PendingQuestion).where(
            PendingQuestion.id == question_id,
            PendingQuestion.business_id == current_user.business_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Pending question not found")

    # Safely extract attributes before any async database operations
    q_id = question.id
    q_question = question.customer_question or ""
    q_source = question.source.value if hasattr(question.source, "value") else str(question.source)
    q_conv_id = question.conversation_id
    q_email_id = question.email_message_id

    question.owner_answer = data.owner_answer
    question.status = PendingQuestionStatus.resolved
    question.resolved_at = datetime.now(timezone.utc)

    # Add answer to knowledge brain & lesson continuous learning
    if data.add_to_brain:
        try:
            await ingest_text(
                db=db,
                business_id=current_user.business_id,
                title=f"Q&A: {q_question[:80]}",
                content=f"Question: {q_question}\n\nAnswer: {data.owner_answer}",
            )
        except Exception as ie:
            logger.error(f"Failed to ingest Q&A to knowledge brain: {ie}")

        from app.models.models import Lesson
        from app.ai.gemini_client import get_embedding
        try:
            lesson_emb = get_embedding(q_question, task_type="RETRIEVAL_DOCUMENT")
            lesson = Lesson(
                business_id=current_user.business_id,
                question=q_question,
                corrected_answer=data.owner_answer,
                original_answer="Thank you! The team will reply to you soon.",
                owner_comment="Added to Brain via Pending Questions",
                embedding=lesson_emb,
                is_active=True,
            )
            db.add(lesson)
        except Exception as le:
            logger.warning(f"Failed to create Lesson embedding: {le}")

    # Re-fetch/ensure question is updated in active session
    await db.commit()
    result_refreshed = await db.execute(
        select(PendingQuestion).where(PendingQuestion.id == q_id)
    )
    question = result_refreshed.scalar_one()
    question.owner_answer = data.owner_answer
    question.status = PendingQuestionStatus.resolved
    question.resolved_at = datetime.now(timezone.utc)

    # Send via original channel
    if data.send_via_channel:
        try:
            if q_source == "chat" and q_conv_id:
                # Post owner's answer into the chat conversation
                owner_msg = Message(
                    conversation_id=q_conv_id,
                    business_id=current_user.business_id,
                    role=MessageRole.owner,
                    content=data.owner_answer,
                )
                db.add(owner_msg)
                # Mark conversation resolved
                conv_result = await db.execute(
                    select(Conversation).where(Conversation.id == q_conv_id)
                )
                conv = conv_result.scalar_one_or_none()
                if conv:
                    conv.is_resolved = True

            elif q_source == "email" and q_email_id:
                # Send reply via Gmail or SMTP
                await send_email_reply(
                    db=db,
                    business_id=current_user.business_id,
                    email_message_id=q_email_id,
                    reply_body=data.owner_answer,
                )
        except Exception as e:
            logger.warning(f"Non-fatal channel reply error: {e}")

    await db.commit()
    await db.refresh(question)
    return question


@router.delete("/{question_id}", status_code=204)
async def dismiss_question(
    question_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(PendingQuestion).where(
            PendingQuestion.id == question_id,
            PendingQuestion.business_id == current_user.business_id,
        )
    )
    question = result.scalar_one_or_none()
    if not question:
        raise HTTPException(404, "Pending question not found")
    await db.delete(question)
    await db.commit()
