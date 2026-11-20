"""
Unified email processing pipeline for Support Brain.
Handles AI draft generation from Knowledge Brain + Lessons, Review vs. Auto mode,
email threading, duplicate prevention, and full bidirectional audit logging.
"""
from typing import List, Optional
from uuid import UUID
import uuid
from datetime import datetime, timezone
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    EmailAccount, EmailMessage, EmailMessageDirection,
    EmailMessageStatus, EmailProcessingMode, PendingQuestion,
    PendingQuestionSource, PendingQuestionStatus, Business, Lesson
)
from app.ai.gemini_client import generate_email_reply, compute_confidence_score
from app.ai.search import search_knowledge, search_lessons
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def format_reply_subject(original_subject: Optional[str]) -> str:
    """Format subject for reply, avoiding stacking Re: Re:."""
    subj = (original_subject or "Inquiry").strip()
    if not subj.lower().startswith("re:"):
        return f"Re: {subj}"
    return subj


async def process_incoming_emails(
    db: AsyncSession,
    emails: List[EmailMessage],
    business: Business,
    account: EmailAccount,
) -> None:
    """
    RAG pipeline for incoming customer emails.
    Generates draft from Lessons + Knowledge Brain and enforces Review vs. Auto mode.
    """
    for email_msg in emails:
        body = email_msg.body_text or email_msg.subject or ""
        if not body.strip():
            continue

        # 1. Search lessons first (highest priority)
        lessons = await search_lessons(db, business.id, body[:1000])
        lesson_answer = None
        lesson_used_id = None
        if lessons:
            lesson_answer = lessons[0]["corrected_answer"]
            lesson_used_id = lessons[0]["lesson_id"]

        # 2. Search knowledge chunks
        knowledge_results = await search_knowledge(db, business.id, body[:1000])
        chunks = [r["content"] for r in knowledge_results]
        top_sim = knowledge_results[0]["similarity"] if knowledge_results else 0.0

        # 3. Generate grounded draft reply
        if lesson_answer:
            draft = f"Thank you for contacting {business.name}.\n\n{lesson_answer}\n\nBest regards,\n{business.name} Support Team"
            confidence = 0.98
        else:
            draft = generate_email_reply(
                customer_email_body=body,
                subject=email_msg.subject or "",
                knowledge_chunks=chunks,
                business_name=business.name,
            )
            confidence = compute_confidence_score(body, draft, top_sim)

        email_msg.draft_reply = draft

        # 4. Enforce processing mode
        if account.processing_mode == EmailProcessingMode.auto:
            if confidence >= settings.SIMILARITY_THRESHOLD and draft.strip() != "Thank you for reaching out. Our team will review your inquiry and respond shortly.":
                # Auto mode with high confidence: dispatch reply immediately
                try:
                    await dispatch_email_reply(
                        db=db,
                        account=account,
                        email_msg=email_msg,
                        reply_body=draft,
                        business_name=business.name,
                    )
                    email_msg.status = EmailMessageStatus.sent
                    email_msg.sent_at = datetime.now(timezone.utc)
                    logger.info(f"Auto-sent email reply to {email_msg.sender} (confidence={confidence:.2f})")
                except Exception as e:
                    logger.error(f"Auto-send failed ({e}), saving as draft")
                    email_msg.status = EmailMessageStatus.draft
            else:
                # Auto mode but low confidence: queue into Pending Questions
                email_msg.status = EmailMessageStatus.draft
                pending = PendingQuestion(
                    business_id=business.id,
                    source=PendingQuestionSource.email,
                    email_message_id=email_msg.id,
                    customer_question=body[:1000],
                    customer_name=email_msg.sender,
                    customer_email=email_msg.sender,
                )
                db.add(pending)
                await db.flush()
                email_msg.pending_question_id = pending.id
                logger.info(f"Low confidence ({confidence:.2f}) email sent to Pending Questions")
        else:
            # Review mode: owner reviews draft before sending
            email_msg.status = EmailMessageStatus.draft


async def dispatch_email_reply(
    db: AsyncSession,
    account: EmailAccount,
    email_msg: EmailMessage,
    reply_body: str,
    business_name: str,
) -> EmailMessage:
    """
    Sends the reply via Gmail API or SMTP depending on account provider.
    Maintains threading, prevents duplicate sends, and saves outgoing message record.
    """
    # Guard: Never send the same reply twice
    if email_msg.status == EmailMessageStatus.sent:
        raise ValueError("This email has already been replied to.")

    subject = format_reply_subject(email_msg.subject)

    # Detect provider
    is_smtp_imap = False
    if account.encrypted_access_token:
        from app.utils.encryption import decrypt_token
        try:
            raw_creds = json.loads(decrypt_token(account.encrypted_access_token))
            if raw_creds.get("provider") == "smtp_imap":
                is_smtp_imap = True
        except Exception:
            pass

    if is_smtp_imap:
        from app.email.smtp_imap_service import send_smtp_message
        send_smtp_message(
            account=account,
            to_email=email_msg.sender,
            subject=subject,
            body=reply_body,
            in_reply_to=email_msg.gmail_message_id,
            references=email_msg.gmail_message_id,
        )
    else:
        # Gmail OAuth API
        from app.email.gmail_service import _build_gmail_service, _send_reply
        service, _ = _build_gmail_service(account)
        await _send_reply(service, email_msg, reply_body, account.email_address)

    now = datetime.now(timezone.utc)

    # 1. Update the incoming message
    email_msg.status = EmailMessageStatus.sent
    email_msg.sent_at = now
    email_msg.draft_reply = reply_body

    # 2. Save outgoing message record (Save every email in and out)
    outgoing_msg = EmailMessage(
        business_id=account.business_id,
        email_account_id=account.id,
        gmail_message_id=f"out-{uuid.uuid4().hex[:12]}",
        gmail_thread_id=email_msg.gmail_thread_id,
        direction=EmailMessageDirection.outgoing,
        subject=subject,
        sender=account.email_address,
        recipient=email_msg.sender,
        body_text=reply_body,
        status=EmailMessageStatus.sent,
        sent_at=now,
        received_at=now,
    )
    db.add(outgoing_msg)

    # If this was tied to a pending question, mark it resolved
    if email_msg.pending_question_id:
        pq_res = await db.execute(
            select(PendingQuestion).where(PendingQuestion.id == email_msg.pending_question_id)
        )
        pq = pq_res.scalar_one_or_none()
        if pq:
            pq.status = PendingQuestionStatus.resolved
            pq.owner_answer = reply_body
            pq.resolved_at = now

    return email_msg
