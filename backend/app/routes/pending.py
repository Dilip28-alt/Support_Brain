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

    if status_filter:
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

    question.owner_answer = data.owner_answer
    question.status = PendingQuestionStatus.resolved
    question.resolved_at = datetime.now(timezone.utc)

    # Add answer to knowledge brain & lesson continuous learning
    if data.add_to_brain:
        await ingest_text(
            db=db,
            business_id=current_user.business_id,
            title=f"Q&A: {question.customer_question[:80]}",
            content=f"Question: {question.customer_question}\n\nAnswer: {data.owner_answer}",
        )
        from app.models.models import Lesson
        from app.ai.gemini_client import get_embedding
        try:
            lesson_emb = get_embedding(question.customer_question, task_type="RETRIEVAL_DOCUMENT")
            lesson = Lesson(
                business_id=current_user.business_id,
                question=question.customer_question,
                corrected_answer=data.owner_answer,
                original_answer="Thank you! The team will reply to you soon.",
                owner_comment="Added to Brain via Pending Questions",
                embedding=lesson_emb,
                is_active=True,
            )
            db.add(lesson)
        except Exception as le:
            pass

    # Send via original channel
    if data.send_via_channel:
        if question.source.value == "chat" and question.conversation_id:
            # Post owner's answer into the chat conversation
            owner_msg = Message(
                conversation_id=question.conversation_id,
                business_id=current_user.business_id,
                role=MessageRole.assistant,
                content=data.owner_answer,
            )
            db.add(owner_msg)
            # Mark conversation resolved
            conv_result = await db.execute(
                select(Conversation).where(Conversation.id == question.conversation_id)
            )
            conv = conv_result.scalar_one_or_none()
            if conv:
                conv.is_resolved = True

        elif question.source.value == "email" and question.email_message_id:
            # Send reply via Gmail
            try:
                await send_email_reply(
                    db=db,
                    business_id=current_user.business_id,
                    email_message_id=question.email_message_id,
                    reply_body=data.owner_answer,
                )
            except Exception as e:
                # Non-fatal — still mark resolved
                pass

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
