"""
Email integration routes — OAuth, SMTP/IMAP, inbox, drafts, sending, and simulation.
"""
from typing import List, Optional
from uuid import UUID
import uuid
from datetime import datetime, timezone
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import get_db
from app.models.models import (
    User, EmailAccount, EmailMessage, Business,
    EmailProcessingMode, EmailAccountStatus, EmailMessageDirection, EmailMessageStatus
)
from app.schemas.email_schema import (
    EmailAccountResponse, EmailAccountUpdate, EmailMessageResponse,
    EmailSendRequest, EmailDraftUpdate, SmtpImapConnectRequest,
    SimulateIncomingEmailRequest, ComposeEmailRequest
)
from app.email.gmail_service import (
    get_authorization_url, handle_oauth_callback,
    fetch_new_emails, send_email_reply
)
from app.utils.auth import get_current_active_user
from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/email", tags=["email"])
settings = get_settings()


# ─────────────────────────────────────────────────────────────
# 1. Connected Accounts (Gmail OAuth & SMTP/IMAP)
# ─────────────────────────────────────────────────────────────

@router.get("/oauth/url")
async def get_oauth_url(
    current_user: User = Depends(get_current_active_user),
):
    """Returns the Gmail OAuth authorization URL."""
    state = str(current_user.business_id)
    url = get_authorization_url(state=state)
    return {"url": url}


@router.get("/oauth/callback")
async def oauth_callback(
    code: str,
    state: str,
    db: AsyncSession = Depends(get_db),
):
    """Handle Gmail OAuth callback. Called by Google after user consent."""
    try:
        business_id = uuid.UUID(state)
    except ValueError:
        raise HTTPException(400, "Invalid state parameter")

    try:
        account = await handle_oauth_callback(db, business_id, code)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/dashboard/email?connected=true"
        )
    except Exception as e:
        raise HTTPException(500, f"OAuth callback failed: {str(e)}")


@router.post("/smtp-imap/connect", response_model=EmailAccountResponse)
async def connect_smtp_imap(
    data: SmtpImapConnectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Connect a custom SMTP/IMAP inbox."""
    from app.email.smtp_imap_service import test_smtp_imap_connection, connect_smtp_imap_account
    ok, msg = test_smtp_imap_connection(
        email_address=data.email_address,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        smtp_host=data.smtp_host,
        smtp_port=data.smtp_port,
        username=data.username,
        password=data.password,
    )
    if not ok:
        raise HTTPException(400, f"Cannot connect to inbox: {msg}")

    account = await connect_smtp_imap_account(
        db=db,
        business_id=current_user.business_id,
        email_address=data.email_address,
        imap_host=data.imap_host,
        imap_port=data.imap_port,
        smtp_host=data.smtp_host,
        smtp_port=data.smtp_port,
        username=data.username,
        password=data.password,
        processing_mode=data.processing_mode,
    )
    return account


@router.get("/accounts", response_model=List[EmailAccountResponse])
async def list_accounts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(EmailAccount).where(EmailAccount.business_id == current_user.business_id)
    )
    return result.scalars().all()


@router.patch("/accounts/{account_id}", response_model=EmailAccountResponse)
async def update_account(
    account_id: UUID,
    data: EmailAccountUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.business_id == current_user.business_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "Email account not found")
    account.processing_mode = data.processing_mode
    await db.commit()
    await db.refresh(account)
    return account


@router.delete("/accounts/{account_id}")
async def delete_account(
    account_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.id == account_id,
            EmailAccount.business_id == current_user.business_id,
        )
    )
    account = result.scalar_one_or_none()
    if not account:
        raise HTTPException(404, "Email account not found")
    await db.delete(account)
    await db.commit()
    return {"message": "Account disconnected"}


# ─────────────────────────────────────────────────────────────
# 2. Fetch & Read Emails
# ─────────────────────────────────────────────────────────────

@router.post("/fetch", status_code=202)
async def fetch_emails(
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Trigger email fetch for all connected accounts (Gmail + IMAP)."""
    accounts_result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.business_id == current_user.business_id,
            EmailAccount.status == EmailAccountStatus.connected,
        )
    )
    accounts = accounts_result.scalars().all()
    if not accounts:
        raise HTTPException(404, "No connected email accounts found")

    biz_result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    business = biz_result.scalar_one()

    for account in accounts:
        # Detect if SMTP/IMAP or Gmail
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
            from app.email.smtp_imap_service import fetch_imap_new_emails
            background_tasks.add_task(fetch_imap_new_emails, db, account, business)
        else:
            background_tasks.add_task(fetch_new_emails, db, account, business)

    return {"message": f"Fetching emails for {len(accounts)} account(s)"}


@router.get("/messages", response_model=List[EmailMessageResponse])
async def list_emails(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
    status_filter: str = None,
    limit: int = 50,
):
    query = select(EmailMessage).where(
        EmailMessage.business_id == current_user.business_id
    ).order_by(EmailMessage.created_at.desc()).limit(limit)

    if status_filter:
        try:
            query = query.where(EmailMessage.status == EmailMessageStatus(status_filter))
        except ValueError:
            pass

    result = await db.execute(query)
    return result.scalars().all()


# ─────────────────────────────────────────────────────────────
# 3. Draft & Send Replies (Review Mode & Threading)
# ─────────────────────────────────────────────────────────────

@router.patch("/messages/{message_id}/draft", response_model=EmailMessageResponse)
async def update_draft(
    message_id: UUID,
    data: EmailDraftUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    result = await db.execute(
        select(EmailMessage).where(
            EmailMessage.id == message_id,
            EmailMessage.business_id == current_user.business_id,
        )
    )
    msg = result.scalar_one_or_none()
    if not msg:
        raise HTTPException(404, "Email message not found")
    msg.draft_reply = data.draft_reply
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/messages/send", response_model=EmailMessageResponse)
async def send_email(
    data: EmailSendRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Owner clicks Send in Review Mode."""
    try:
        return await send_email_reply(
            db=db,
            business_id=current_user.business_id,
            email_message_id=data.email_message_id,
            reply_body=data.reply_body,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))


# ─────────────────────────────────────────────────────────────
# 4. Compose Direct Email & Simulate Customer Incoming Email
# ─────────────────────────────────────────────────────────────

@router.post("/compose", response_model=EmailMessageResponse)
async def compose_email(
    data: ComposeEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """Directly compose and send an outgoing email from the connected inbox."""
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.business_id == current_user.business_id,
            EmailAccount.status == EmailAccountStatus.connected,
        )
    )
    account = result.scalars().first()
    if not account:
        raise HTTPException(400, "Please connect an email inbox (Gmail or SMTP/IMAP) first")

    # Check if SMTP or Gmail
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
        try:
            send_smtp_message(
                account=account,
                to_email=data.recipient,
                subject=data.subject,
                body=data.body,
            )
        except Exception as e:
            raise HTTPException(500, f"SMTP send failed: {str(e)}")
    else:
        from app.email.gmail_service import _build_gmail_service
        from email.mime.text import MIMEText
        import base64
        try:
            service, _ = _build_gmail_service(account)
            mime = MIMEText(data.body)
            mime["to"] = data.recipient
            mime["from"] = account.email_address
            mime["subject"] = data.subject
            raw = base64.urlsafe_b64encode(mime.as_bytes()).decode("utf-8")
            service.users().messages().send(userId="me", body={"raw": raw}).execute()
        except Exception as e:
            logger.warning(f"Gmail send error: {e}")

    now = datetime.now(timezone.utc)
    thread_id = f"thread-{uuid.uuid4().hex[:12]}"
    msg = EmailMessage(
        business_id=current_user.business_id,
        email_account_id=account.id,
        gmail_message_id=f"out-{uuid.uuid4().hex[:12]}",
        gmail_thread_id=thread_id,
        direction=EmailMessageDirection.outgoing,
        subject=data.subject,
        sender=account.email_address,
        recipient=data.recipient,
        body_text=data.body,
        status=EmailMessageStatus.sent,
        sent_at=now,
        received_at=now,
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)
    return msg


@router.post("/simulate-incoming", response_model=EmailMessageResponse)
async def simulate_incoming_email(
    data: SimulateIncomingEmailRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    Simulates a new incoming customer email.
    Instantly runs through Knowledge Brain + Lessons, generates a draft,
    and handles Review mode vs. Auto mode (auto-sending or sending to Pending).
    """
    result = await db.execute(
        select(EmailAccount).where(EmailAccount.business_id == current_user.business_id)
    )
    account = result.scalars().first()
    if not account:
        biz_res = await db.execute(
            select(Business).where(Business.id == current_user.business_id)
        )
        biz_obj = biz_res.scalar_one()
        account = EmailAccount(
            business_id=current_user.business_id,
            email_address=f"support@{biz_obj.slug}.com",
            processing_mode=EmailProcessingMode.review,
            status=EmailAccountStatus.connected,
        )
        db.add(account)
        await db.flush()

    biz_result = await db.execute(
        select(Business).where(Business.id == current_user.business_id)
    )
    business = biz_result.scalar_one()

    msg_id = f"sim-{uuid.uuid4().hex[:12]}"
    thread_id = f"thread-{uuid.uuid4().hex[:12]}"
    now = datetime.now(timezone.utc)

    email_msg = EmailMessage(
        business_id=current_user.business_id,
        email_account_id=account.id,
        gmail_message_id=msg_id,
        gmail_thread_id=thread_id,
        direction=EmailMessageDirection.incoming,
        subject=data.subject,
        sender=f"{data.sender_name} <{data.sender_email}>",
        recipient=account.email_address,
        body_text=data.body,
        status=EmailMessageStatus.pending,
        received_at=now,
    )
    db.add(email_msg)
    await db.flush()

    from app.email.email_processing import process_incoming_emails
    await process_incoming_emails(db, [email_msg], business, account)

    await db.commit()
    await db.refresh(email_msg)
    return email_msg
