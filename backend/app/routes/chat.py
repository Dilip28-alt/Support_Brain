"""
Chat routes — public chat endpoint and authenticated conversation management.
"""
from typing import List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.models import (
    User, Conversation, Message, Business,
    EmailAccount, EmailMessage, EmailMessageDirection,
    EmailMessageStatus, EmailProcessingMode, EmailAccountStatus
)
from app.schemas.chat import (
    ChatRequest, ChatResponse, ConversationResponse, MessageResponse,
    FeedbackCreate, AskAgainRequest, AskAgainResponse, PublicBusinessInfo,
    PublicEmailInquiryRequest, PublicEmailInquiryResponse,
    ChatEmailTranscriptRequest, ChatEmailTranscriptResponse
)
from app.services.chat_service import handle_chat, handle_ask_again, save_feedback
from app.utils.auth import get_current_active_user
import uuid
from datetime import datetime, timezone

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

    # Fetch connected support email if available
    acc_res = await db.execute(
        select(EmailAccount).where(
            EmailAccount.business_id == business.id,
            EmailAccount.status == EmailAccountStatus.connected,
        )
    )
    acc = acc_res.scalars().first()
    support_email = acc.email_address if acc else f"support@{business.slug}.com"

    return PublicBusinessInfo(
        name=business.name,
        slug=business.slug,
        widget_token=business.widget_token or "",
        description=business.description,
        support_email=support_email,
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


@router.post("/api/chat/public/email-inquiry", response_model=PublicEmailInquiryResponse)
async def public_email_inquiry(
    inquiry: PublicEmailInquiryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Public customer email inquiry endpoint.
    Allows customers on the public chat link to submit questions via email.
    Saves incoming email, automatically drafts reply using RAG & Lessons,
    and dispatches or routes to Review Mode / Pending Questions.
    """
    # 1. Resolve business
    business = None
    if inquiry.business_token:
        res = await db.execute(
            select(Business).where(Business.widget_token == inquiry.business_token.strip(), Business.is_active == True)
        )
        business = res.scalar_one_or_none()
    elif inquiry.business_slug:
        res = await db.execute(
            select(Business).where(Business.slug.ilike(inquiry.business_slug.strip()), Business.is_active == True)
        )
        business = res.scalar_one_or_none()

    if not business:
        raise HTTPException(404, "Business not found or inactive")

    # 2. Find or establish email account
    acc_res = await db.execute(
        select(EmailAccount).where(EmailAccount.business_id == business.id)
    )
    account = acc_res.scalars().first()
    if not account:
        account = EmailAccount(
            business_id=business.id,
            email_address=f"support@{business.slug}.com",
            processing_mode=EmailProcessingMode.review,
            status=EmailAccountStatus.connected,
        )
        db.add(account)
        await db.flush()

    # 3. Create incoming EmailMessage record
    now = datetime.now(timezone.utc)
    msg_id = f"pub-{uuid.uuid4().hex[:12]}"
    thread_id = f"thread-{uuid.uuid4().hex[:12]}"
    sender_display = (
        f"{inquiry.sender_name.strip()} <{inquiry.sender_email.strip()}>"
        if inquiry.sender_name
        else inquiry.sender_email.strip()
    )

    email_msg = EmailMessage(
        business_id=business.id,
        email_account_id=account.id,
        gmail_message_id=msg_id,
        gmail_thread_id=thread_id,
        direction=EmailMessageDirection.incoming,
        subject=inquiry.subject.strip(),
        sender=sender_display,
        recipient=account.email_address,
        body_text=inquiry.message.strip(),
        status=EmailMessageStatus.pending,
        received_at=now,
    )
    db.add(email_msg)
    await db.flush()

    # 4. Run Knowledge Brain + Lessons drafting pipeline
    from app.email.email_processing import process_incoming_emails
    await process_incoming_emails(db, [email_msg], business, account)

    await db.commit()
    await db.refresh(email_msg)

    return PublicEmailInquiryResponse(
        status="success",
        message=f"Thank you, {inquiry.sender_name or 'customer'}! Your email inquiry has been received by {business.name}. We will review it and reply directly to {inquiry.sender_email}.",
        email_id=email_msg.id,
        thread_id=thread_id,
    )


@router.post("/api/chat/public/email-transcript", response_model=ChatEmailTranscriptResponse)
async def public_email_transcript(
    data: ChatEmailTranscriptRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Send chat answer or full transcript to customer's email inbox.
    Uses the business's connected Gmail or SMTP inbox and records the outgoing email in history.
    """
    # 1. Resolve business
    business = None
    if data.business_token:
        res = await db.execute(
            select(Business).where(Business.widget_token == data.business_token.strip(), Business.is_active == True)
        )
        business = res.scalar_one_or_none()
    elif data.business_slug:
        res = await db.execute(
            select(Business).where(Business.slug.ilike(data.business_slug.strip()), Business.is_active == True)
        )
        business = res.scalar_one_or_none()

    if not business:
        raise HTTPException(404, "Business not found or inactive")

    # 2. Get connected inbox
    acc_res = await db.execute(
        select(EmailAccount).where(
            EmailAccount.business_id == business.id,
            EmailAccount.status == EmailAccountStatus.connected,
        )
    )
    account = acc_res.scalars().first()
    if not account:
        raise HTTPException(400, f"No email account connected for {business.name}. Please connect an inbox in settings.")

    # 3. Format subject and body
    recipient = data.recipient_email.strip()
    customer_name = data.customer_name.strip() if data.customer_name else "Customer"

    if data.question and data.answer:
        subject = f"Support Brain Answer: {data.question[:50]}"
        content_section = f"Question:\n{data.question}\n\nAI Support Answer:\n{data.answer}"
    elif data.full_transcript:
        subject = f"{business.name} Support — Chat Conversation Transcript"
        content_section = data.full_transcript
    else:
        subject = f"{business.name} Support Conversation"
        content_section = data.answer or "Here is your support conversation."

    email_body = (
        f"Hello {customer_name},\n\n"
        f"Thank you for reaching out to {business.name} support! Here is a copy of your chat response:\n\n"
        f"--------------------------------------------------\n"
        f"{content_section}\n"
        f"--------------------------------------------------\n\n"
        f"If you have further questions or require additional assistance, feel free to reply directly to this email.\n\n"
        f"Best regards,\n"
        f"{business.name} Support Team\n"
        f"Powered by Support Brain"
    )

    # 4. Detect provider & send email
    is_smtp_imap = False
    if account.encrypted_access_token:
        from app.utils.encryption import decrypt_token
        import json
        try:
            raw_creds = json.loads(decrypt_token(account.encrypted_access_token))
            if raw_creds.get("provider") == "smtp_imap":
                is_smtp_imap = True
        except Exception:
            pass

    gmail_thread_id = None
    if is_smtp_imap:
        from app.email.smtp_imap_service import send_smtp_message
        try:
            send_smtp_message(
                account=account,
                to_email=recipient,
                subject=subject,
                body=email_body,
            )
        except Exception as e:
            raise HTTPException(500, f"Failed to send email via SMTP: {str(e)}")
    else:
        # Gmail API
        import base64
        from email.mime.text import MIMEText
        from app.email.gmail_service import _build_gmail_service

        msg = MIMEText(email_body)
        msg["to"] = recipient
        msg["from"] = account.email_address
        msg["subject"] = subject

        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        try:
            service, _ = _build_gmail_service(account)
            sent_resp = service.users().messages().send(userId="me", body={"raw": raw}).execute()
            if sent_resp and sent_resp.get("threadId"):
                gmail_thread_id = sent_resp["threadId"]
        except Exception as e:
            raise HTTPException(500, f"Failed to send email via Gmail: {str(e)}")

    # 5. Record outgoing email in email_messages
    now = datetime.now(timezone.utc)
    outgoing_msg = EmailMessage(
        business_id=business.id,
        email_account_id=account.id,
        gmail_message_id=f"out-{uuid.uuid4().hex[:12]}",
        gmail_thread_id=gmail_thread_id or f"thread-{uuid.uuid4().hex[:12]}",
        direction=EmailMessageDirection.outgoing,
        subject=subject,
        sender=account.email_address,
        recipient=recipient,
        body_text=email_body,
        status=EmailMessageStatus.sent,
        sent_at=now,
        received_at=now,
    )
    db.add(outgoing_msg)
    await db.commit()

    return ChatEmailTranscriptResponse(
        status="success",
        message=f"Chat response sent successfully to {recipient}!"
    )


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
