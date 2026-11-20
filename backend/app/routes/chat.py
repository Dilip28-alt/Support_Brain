"""
Chat routes — public chat endpoint and authenticated conversation management.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import User, Conversation, Message, Business
from app.schemas.chat import (
    ChatRequest, ChatResponse, ConversationResponse, MessageResponse,
    FeedbackCreate, AskAgainRequest, AskAgainResponse, PublicBusinessInfo
)
from app.services.chat_service import handle_chat, handle_ask_again, save_feedback
from app.utils.auth import get_current_active_user

router = APIRouter(tags=["chat"])

# ─────── Public chat (no auth required) ───────

@router.get("/api/chat/public/info", response_model=PublicBusinessInfo)
async def get_public_business_info(
    token: Optional[str] = None,
    slug: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    """
    Public business metadata for widget and chat window.
    Never exposes owner dashboard, private documents, or credentials.
    """
    if not token and not slug:
        raise HTTPException(400, "Either 'token' or 'slug' parameter is required")

    business = None
    if token:
        result = await db.execute(select(Business).where(Business.widget_token == token.strip(), Business.is_active == True))
        business = result.scalar_one_or_none()
    elif slug:
        result = await db.execute(select(Business).where(Business.slug.ilike(slug.strip()), Business.is_active == True))
        business = result.scalar_one_or_none()

    if not business:
        raise HTTPException(404, "Business not found or inactive")

    return PublicBusinessInfo(
        name=business.name,
        slug=business.slug,
        widget_token=business.widget_token or "",
        description=business.description,
    )


@router.get("/api/widget/{slug}")
async def get_widget_info_by_slug(slug: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint for customer widget by slug."""
    info = await get_public_business_info(slug=slug, db=db)
    return {
        "business_name": info.name,
        "business_slug": info.slug,
        "widget_token": info.widget_token,
        "description": info.description,
    }


@router.get("/api/widget/token/{token}")
async def get_widget_info_by_token(token: str, db: AsyncSession = Depends(get_db)):
    """Public endpoint for customer widget by public widget token."""
    info = await get_public_business_info(token=token, db=db)
    return {
        "business_name": info.name,
        "business_slug": info.slug,
        "widget_token": info.widget_token,
        "description": info.description,
    }


@router.post("/api/chat", response_model=ChatResponse)
async def public_chat(
    request: Request,
    chat_req: ChatRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public customer chat endpoint — no auth required.
    Validates business via public widget token or slug.
    Never trusts raw business_id.
    """
    try:
        return await handle_chat(
            db=db,
            business_slug=chat_req.business_slug,
            business_token=chat_req.business_token,
            question=chat_req.question,
            customer_name=chat_req.customer_name,
            customer_email=chat_req.customer_email,
            conversation_id=chat_req.conversation_id,
        )
    except ValueError as e:
        import logging
        logging.getLogger("support_brain").error(f"Chat ValueError: {e}", exc_info=True)
        raise HTTPException(404, str(e))
    except Exception as e:
        import logging
        logging.getLogger("support_brain").error(f"Chat unexpected error: {e}", exc_info=True)
        raise HTTPException(500, str(e))


# ─────── Authenticated dashboard ───────

@router.get("/api/conversations", response_model=List[ConversationResponse])
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    limit: int = 50,
    offset: int = 0,
):
    result = await db.execute(
        select(Conversation)
        .where(Conversation.business_id == current_user.business_id)
        .order_by(Conversation.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    conversations = result.scalars().all()

    # Attach message counts
    output = []
    for conv in conversations:
        count_result = await db.execute(
            select(func.count(Message.id)).where(Message.conversation_id == conv.id)
        )
        count = count_result.scalar() or 0
        resp = ConversationResponse(
            id=conv.id,
            business_id=conv.business_id,
            customer_name=conv.customer_name,
            customer_email=conv.customer_email,
            is_resolved=conv.is_resolved,
            created_at=conv.created_at,
            message_count=count,
        )
        output.append(resp)
    return output


@router.get("/api/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
async def get_messages(
    conversation_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    # Verify ownership
    conv_result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.business_id == current_user.business_id,
        )
    )
    if not conv_result.scalar_one_or_none():
        raise HTTPException(404, "Conversation not found")

    result = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    return result.scalars().all()


@router.post("/api/feedback", status_code=201)
async def submit_feedback(
    data: FeedbackCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await save_feedback(
        db=db,
        business_id=current_user.business_id,
        message_id=data.message_id,
        conversation_id=data.conversation_id,
        feedback_type=data.feedback_type,
        question=data.question,
        ai_answer=data.ai_answer,
        correct_answer=data.correct_answer,
        owner_comment=data.owner_comment,
    )
    return result


@router.post("/api/ask-again", response_model=AskAgainResponse)
async def ask_again(
    data: AskAgainRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    biz_result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    business = biz_result.scalar_one()
    try:
        return await handle_ask_again(
            db=db,
            business_id=current_user.business_id,
            business_name=business.name,
            message_id=data.message_id,
            conversation_id=data.conversation_id,
            question=data.question,
        )
    except ValueError as e:
        raise HTTPException(404, str(e))


@router.get("/api/widget/{business_slug}")
async def get_widget_config(
    business_slug: str,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint returning business config for the chat widget."""
    result = await db.execute(
        select(Business).where(Business.slug == business_slug, Business.is_active == True)
    )
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(404, "Business not found")
    return {
        "business_name": business.name,
        "business_slug": business.slug,
    }
