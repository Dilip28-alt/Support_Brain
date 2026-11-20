"""
Chat service — the main RAG pipeline.
Order of operations:
  1. Search active lessons (highest priority)
  2. Search knowledge chunks
  3. Generate answer
  4. Compute confidence
  5. Create pending question if confidence < threshold
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import json
import logging

from app.models.models import (
    Business, Conversation, Message, PendingQuestion,
    MessageRole, PendingQuestionSource, PendingQuestionStatus,
    Lesson, LessonUsage, AnswerFeedback, FeedbackType
)
from app.ai.gemini_client import (
    generate_answer, compute_confidence_score, get_embedding
)
from app.ai.search import search_knowledge, search_lessons
from app.config import get_settings
from app.schemas.chat import ChatResponse, SourceChunk, AskAgainResponse

logger = logging.getLogger(__name__)
settings = get_settings()

FALLBACK_ANSWER = "Thank you! The team will reply to you soon."


async def handle_chat(
    db: AsyncSession,
    business_slug: Optional[str] = None,
    business_token: Optional[str] = None,
    question: str = "",
    customer_name: Optional[str] = None,
    customer_email: Optional[str] = None,
    conversation_id: Optional[UUID] = None,
) -> ChatResponse:
    """Main RAG pipeline for public customer chat."""

    # 1. Resolve and validate business using public token or slug
    business = None
    if business_token and business_token.strip():
        token_clean = business_token.strip()
        result = await db.execute(
            select(Business).where(
                Business.widget_token == token_clean,
                Business.is_active == True
            )
        )
        business = result.scalar_one_or_none()

    if not business and business_slug and business_slug.strip():
        clean_slug = business_slug.strip()
        result = await db.execute(
            select(Business).where(
                Business.slug.ilike(clean_slug),
                Business.is_active == True
            )
        )
        business = result.scalar_one_or_none()
        if not business:
            alt = await db.execute(select(Business).where(Business.slug.ilike(clean_slug)))
            business = alt.scalar_one_or_none()

    if not business:
        identifier = business_token or business_slug or "unspecified"
        raise ValueError(f"Business identifier '{identifier}' is invalid or unauthorized")

    # 2. Get or create conversation
    if conversation_id:
        conv_result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.business_id == business.id,
            )
        )
        conversation = conv_result.scalar_one_or_none()
    else:
        conversation = None

    if not conversation:
        conversation = Conversation(
            business_id=business.id,
            customer_name=customer_name,
            customer_email=customer_email,
        )
        db.add(conversation)
        await db.flush()

    # 3. Save user message
    user_msg = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        role=MessageRole.user,
        content=question,
    )
    db.add(user_msg)
    await db.flush()

    # 4. Search lessons first
    lessons = await search_lessons(db, business.id, question)
    lesson_used_id = None
    lesson_answer = None

    if lessons:
        best_lesson = lessons[0]
        lesson_used_id = best_lesson["lesson_id"]
        lesson_answer = best_lesson["corrected_answer"]

        # Increment lesson usage count
        lesson_result = await db.execute(
            select(Lesson).where(Lesson.id == lesson_used_id)
        )
        lesson_obj = lesson_result.scalar_one_or_none()
        if lesson_obj:
            lesson_obj.usage_count += 1

        # Track lesson usage
        usage = LessonUsage(
            business_id=business.id,
            lesson_id=lesson_used_id,
            conversation_id=conversation.id,
            question=question,
        )
        db.add(usage)

    # 5. Search knowledge chunks
    knowledge_results = await search_knowledge(db, business.id, question)
    knowledge_chunks = [r["content"] for r in knowledge_results]
    top_similarity = knowledge_results[0]["similarity"] if knowledge_results else 0.0

    # 6. Generate answer
    answer = generate_answer(
        question=question,
        knowledge_chunks=knowledge_chunks,
        business_name=business.name,
        lesson_answer=lesson_answer,
    )

    # 7. Compute confidence and check if question is pending
    if lesson_answer:
        confidence = 0.98
        is_pending = False
    elif knowledge_chunks and answer.strip() != FALLBACK_ANSWER:
        confidence = compute_confidence_score(question, answer, top_similarity)
        is_pending = (confidence < settings.SIMILARITY_THRESHOLD)
        if is_pending:
            # Low confidence means relevant information is not sufficient -> respond with fallback
            answer = FALLBACK_ANSWER
    else:
        confidence = 0.0
        is_pending = True
        answer = FALLBACK_ANSWER

    # 8. Save assistant message
    source_chunks_json = json.dumps([
        {"chunk_id": str(r["chunk_id"]), "similarity": r["similarity"]}
        for r in knowledge_results
    ])
    assistant_msg = Message(
        conversation_id=conversation.id,
        business_id=business.id,
        role=MessageRole.assistant,
        content=answer,
        source_chunks=source_chunks_json,
        lesson_id=lesson_used_id,
        confidence_score=confidence,
    )
    db.add(assistant_msg)
    await db.flush()

    # 9. Create pending question if needed
    if is_pending:
        pending = PendingQuestion(
            business_id=business.id,
            source=PendingQuestionSource.chat,
            conversation_id=conversation.id,
            customer_question=question,
            customer_name=customer_name,
            customer_email=customer_email,
        )
        db.add(pending)

    await db.commit()
    await db.refresh(assistant_msg)

    source_chunk_list = [] if is_pending else [
        SourceChunk(
            chunk_id=r["chunk_id"],
            source_title=r.get("source_title"),
            content=r["content"],
            similarity=r["similarity"],
        )
        for r in knowledge_results
    ]

    return ChatResponse(
        conversation_id=conversation.id,
        message_id=assistant_msg.id,
        answer=answer,
        source_chunks=source_chunk_list,
        lesson_used=lesson_used_id,
        confidence_score=confidence,
        is_pending=is_pending,
    )


async def handle_ask_again(
    db: AsyncSession,
    business_id: UUID,
    business_name: str,
    message_id: Optional[UUID] = None,
    conversation_id: Optional[UUID] = None,
    question: Optional[str] = None,
) -> AskAgainResponse:
    """Re-run a question through the current learning system and compare answers."""
    assistant_msg = None
    previous_answer = "N/A"
    original_question = question

    if message_id:
        assistant_result = await db.execute(
            select(Message).where(
                Message.id == message_id,
                Message.business_id == business_id,
            )
        )
        assistant_msg = assistant_result.scalar_one_or_none()
        if assistant_msg:
            previous_answer = assistant_msg.content

    if not original_question and conversation_id and assistant_msg:
        # Find the user message directly preceding this assistant message
        user_msg_result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.user,
                Message.business_id == business_id,
                Message.created_at <= assistant_msg.created_at,
            ).order_by(Message.created_at.desc())
        )
        user_msgs = user_msg_result.scalars().all()
        if user_msgs:
            original_question = user_msgs[0].content

    if not original_question and conversation_id:
        # Fallback to most recent user message in conversation
        user_msg_result = await db.execute(
            select(Message).where(
                Message.conversation_id == conversation_id,
                Message.role == MessageRole.user,
                Message.business_id == business_id,
            ).order_by(Message.created_at.desc())
        )
        user_msgs = user_msg_result.scalars().all()
        if user_msgs:
            original_question = user_msgs[0].content

    if not original_question:
        raise ValueError("Original question not found. Please provide question or valid message_id.")

    # Re-run through the current pipeline
    lessons = await search_lessons(db, business_id, original_question)
    lesson_used_id = None
    lesson_answer = None
    knowledge_source_used = None

    if lessons:
        best_lesson = lessons[0]
        lesson_used_id = best_lesson["lesson_id"]
        lesson_answer = best_lesson["corrected_answer"]

    knowledge_results = await search_knowledge(db, business_id, original_question)
    knowledge_chunks = [r["content"] for r in knowledge_results]
    if knowledge_results:
        knowledge_source_used = knowledge_results[0].get("source_title")

    top_similarity = knowledge_results[0]["similarity"] if knowledge_results else 0.0

    new_answer = generate_answer(
        question=original_question,
        knowledge_chunks=knowledge_chunks,
        business_name=business_name,
        lesson_answer=lesson_answer,
    )

    return AskAgainResponse(
        original_question=original_question,
        previous_answer=previous_answer,
        new_answer=new_answer,
        lesson_used=lesson_used_id,
        knowledge_source_used=knowledge_source_used,
        lesson_retrieved=lesson_used_id is not None,
    )


async def save_feedback(
    db: AsyncSession,
    business_id: UUID,
    message_id: UUID,
    conversation_id: UUID,
    feedback_type: str,
    question: Optional[str],
    ai_answer: Optional[str],
    correct_answer: Optional[str],
    owner_comment: Optional[str],
) -> dict:
    """Save feedback and optionally create a lesson for bad answers."""
    fb_enum = FeedbackType.good if feedback_type == "good" else FeedbackType.bad
    lesson_id = None

    # If question or ai_answer was omitted by the frontend, retrieve them from conversation history
    if (not question or not ai_answer) and conversation_id and message_id:
        msg_res = await db.execute(
            select(Message).where(Message.id == message_id, Message.business_id == business_id)
        )
        ast_msg = msg_res.scalar_one_or_none()
        if ast_msg:
            if not ai_answer:
                ai_answer = ast_msg.content
            if not question:
                user_msg_result = await db.execute(
                    select(Message).where(
                        Message.conversation_id == conversation_id,
                        Message.role == MessageRole.user,
                        Message.business_id == business_id,
                        Message.created_at <= ast_msg.created_at,
                    ).order_by(Message.created_at.desc())
                )
                u_msg = user_msg_result.scalars().first()
                if u_msg:
                    question = u_msg.content

    # Save feedback record
    feedback = AnswerFeedback(
        business_id=business_id,
        conversation_id=conversation_id,
        message_id=message_id,
        feedback_type=fb_enum,
        question=question,
        ai_answer=ai_answer,
        correct_answer=correct_answer,
        owner_comment=owner_comment,
    )
    db.add(feedback)

    # For bad feedback, create a lesson
    if fb_enum == FeedbackType.bad and correct_answer and question:
        embedding = get_embedding(question, task_type="RETRIEVAL_DOCUMENT")
        lesson = Lesson(
            business_id=business_id,
            question=question,
            original_answer=ai_answer,
            corrected_answer=correct_answer,
            owner_comment=owner_comment,
            embedding=embedding,
            is_active=True,
        )
        db.add(lesson)
        await db.flush()
        lesson_id = lesson.id
        feedback.lesson_created = True
        feedback.lesson_id = lesson_id

    await db.commit()
    return {"lesson_created": fb_enum == FeedbackType.bad and correct_answer is not None, "lesson_id": lesson_id}
