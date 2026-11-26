"""
Gmail OAuth and email processing service.
"""
from typing import Optional, List
from uuid import UUID
from datetime import datetime, timezone
import base64
import json
import logging

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    EmailAccount, EmailMessage, EmailAccountStatus,
    EmailMessageDirection, EmailMessageStatus,
    PendingQuestion, PendingQuestionSource, Business,
    EmailProcessingMode
)
from app.ai.gemini_client import generate_email_reply, compute_confidence_score
from app.ai.search import search_knowledge
from app.utils.encryption import encrypt_token, decrypt_token
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.modify",
]


def get_oauth_flow(redirect_uri: Optional[str] = None) -> Flow:
    """Build a Google OAuth2 flow."""
    effective_redirect = redirect_uri or settings.effective_gmail_redirect_uri
    client_config = {
        "web": {
            "client_id": settings.GMAIL_CLIENT_ID,
            "client_secret": settings.GMAIL_CLIENT_SECRET,
            "redirect_uris": [
                effective_redirect,
                "https://support-brain-api.onrender.com/api/email/oauth/callback",
                "http://localhost:8000/api/email/oauth/callback",
            ],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = Flow.from_client_config(
        client_config,
        scopes=GMAIL_SCOPES,
        redirect_uri=effective_redirect,
    )
    return flow


def get_authorization_url(state: str, redirect_uri: Optional[str] = None) -> str:
    """Generate the Gmail OAuth authorization URL."""
    flow = get_oauth_flow(redirect_uri=redirect_uri)
    auth_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        prompt="consent",   # always prompt to get refresh token
    )
    return auth_url


async def handle_oauth_callback(
    db: AsyncSession,
    business_id: UUID,
    code: str,
    redirect_uri: Optional[str] = None,
) -> EmailAccount:
    """Exchange OAuth code for tokens and store encrypted tokens."""
    flow = get_oauth_flow(redirect_uri=redirect_uri)
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Get email address from Google
    service = build("gmail", "v1", credentials=creds)
    profile = service.users().getProfile(userId="me").execute()
    email_address = profile.get("emailAddress", "")

    # Check if already connected
    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.business_id == business_id,
            EmailAccount.email_address == email_address,
        )
    )
    account = result.scalar_one_or_none()

    encrypted_access = encrypt_token(creds.token)
    encrypted_refresh = encrypt_token(creds.refresh_token) if creds.refresh_token else None

    if account:
        account.encrypted_access_token = encrypted_access
        if encrypted_refresh:
            account.encrypted_refresh_token = encrypted_refresh
        account.token_expiry = creds.expiry
        account.status = EmailAccountStatus.connected
    else:
        account = EmailAccount(
            business_id=business_id,
            email_address=email_address,
            encrypted_access_token=encrypted_access,
            encrypted_refresh_token=encrypted_refresh,
            token_expiry=creds.expiry,
            status=EmailAccountStatus.connected,
        )
        db.add(account)

    await db.commit()
    await db.refresh(account)
    return account


def _build_gmail_service(account: EmailAccount):
    """Build a Gmail API service with token refresh."""
    if not account.encrypted_access_token:
        raise ValueError("No access token stored for this account")

    access_token = decrypt_token(account.encrypted_access_token)
    refresh_token = None
    if account.encrypted_refresh_token:
        refresh_token = decrypt_token(account.encrypted_refresh_token)

    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GMAIL_CLIENT_ID,
        client_secret=settings.GMAIL_CLIENT_SECRET,
        scopes=GMAIL_SCOPES,
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as e:
            err_str = str(e).lower()
            if "invalid_grant" in err_str or "token has been expired" in err_str or "refresherror" in err_str:
                raise ValueError("Gmail authorization has expired or was revoked by Google. Please click 'Connect Gmail' in the dashboard to reconnect your account.")
            raise

    return build("gmail", "v1", credentials=creds), creds


def _extract_body(payload) -> tuple[str, str]:
    """Extract text and HTML body from Gmail message payload."""
    text_body = ""
    html_body = ""

    def _walk(part):
        nonlocal text_body, html_body
        mime = part.get("mimeType", "")
        body_data = part.get("body", {}).get("data", "")

        if mime == "text/plain" and body_data:
            text_body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")
        elif mime == "text/html" and body_data:
            html_body = base64.urlsafe_b64decode(body_data).decode("utf-8", errors="replace")

        for sub in part.get("parts", []):
            _walk(sub)

    _walk(payload)
    return text_body, html_body


async def fetch_new_emails(
    db: AsyncSession,
    account: EmailAccount,
    business: Business,
) -> List[EmailMessage]:
    """Poll Gmail for new messages not yet stored."""
    try:
        service, creds = _build_gmail_service(account)
    except Exception as e:
        logger.error(f"Gmail auth failed for {account.email_address}: {e}")
        account.status = EmailAccountStatus.error
        await db.commit()
        return []

    query = "is:unread in:inbox"
    messages_meta = service.users().messages().list(
        userId="me", q=query, maxResults=20
    ).execute()

    message_ids = [m["id"] for m in messages_meta.get("messages", [])]
    new_emails = []

    for msg_id in message_ids:
        # Idempotency: skip if already stored
        existing = await db.execute(
            select(EmailMessage).where(EmailMessage.gmail_message_id == msg_id)
        )
        if existing.scalar_one_or_none():
            continue

        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
        except HttpError as e:
            logger.error(f"Failed to fetch message {msg_id}: {e}")
            continue

        headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "")
        recipient = headers.get("To", "")
        thread_id = msg.get("threadId", "")
        internal_date = msg.get("internalDate")
        received_at = (
            datetime.fromtimestamp(int(internal_date) / 1000, tz=timezone.utc)
            if internal_date else None
        )

        text_body, html_body = _extract_body(msg.get("payload", {}))

        email_msg = EmailMessage(
            business_id=account.business_id,
            email_account_id=account.id,
            gmail_message_id=msg_id,
            gmail_thread_id=thread_id,
            direction=EmailMessageDirection.incoming,
            subject=subject,
            sender=sender,
            recipient=recipient,
            body_text=text_body,
            body_html=html_body,
            status=EmailMessageStatus.pending,
            received_at=received_at,
        )
        db.add(email_msg)
        new_emails.append(email_msg)

    if new_emails:
        await db.flush()
        # Generate reply drafts using unified RAG pipeline (Lessons + Knowledge Brain)
        from app.email.email_processing import process_incoming_emails
        await process_incoming_emails(db, new_emails, business, account)

    await db.commit()
    return new_emails


async def _generate_drafts(
    db: AsyncSession,
    emails: List[EmailMessage],
    business: Business,
    account: EmailAccount,
    service,
):
    """Generate AI reply drafts for incoming emails."""
    for email_msg in emails:
        body = email_msg.body_text or ""
        if not body.strip():
            continue

        knowledge_results = await search_knowledge(db, business.id, body[:1000])
        chunks = [r["content"] for r in knowledge_results]
        top_sim = knowledge_results[0]["similarity"] if knowledge_results else 0.0

        draft = generate_email_reply(
            customer_email_body=body,
            subject=email_msg.subject or "",
            knowledge_chunks=chunks,
            business_name=business.name,
        )
        confidence = compute_confidence_score(body, draft, top_sim)
        email_msg.draft_reply = draft

        if account.processing_mode == EmailProcessingMode.auto:
            if confidence >= settings.SIMILARITY_THRESHOLD:
                # Auto-send
                try:
                    await _send_reply(service, email_msg, draft, account.email_address)
                    email_msg.status = EmailMessageStatus.sent
                    email_msg.sent_at = datetime.now(timezone.utc)
                except Exception as e:
                    logger.error(f"Auto-send failed: {e}")
                    email_msg.status = EmailMessageStatus.draft
            else:
                # Low confidence → pending question
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
        else:
            # Review mode → just save draft
            email_msg.status = EmailMessageStatus.draft


async def _send_reply(service, email_msg: EmailMessage, reply_body: str, from_email: str):
    """Send a reply in the same Gmail thread, or start a new thread if threadId is synthetic."""
    import email as email_lib
    from email.mime.text import MIMEText

    msg = MIMEText(reply_body)
    msg["to"] = email_msg.sender
    msg["from"] = from_email
    subject = email_msg.subject or ""
    msg["subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    mid = email_msg.gmail_message_id
    is_synthetic_mid = not mid or mid.startswith("pub-") or mid.startswith("sim-")
    if not is_synthetic_mid:
        msg["In-Reply-To"] = mid
        msg["References"] = mid

    raw = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

    # Check if threadId is a genuine Google Gmail thread ID
    # Google thread IDs are hex strings without prefixes like 'thread-' or 'sim-'
    tid = email_msg.gmail_thread_id
    is_synthetic = not tid or tid.startswith("thread-") or tid.startswith("sim-") or not all(c in "0123456789abcdefABCDEF" for c in tid)

    body = {"raw": raw}
    if not is_synthetic:
        body["threadId"] = tid

    try:
        sent_resp = service.users().messages().send(userId="me", body=body).execute()
    except HttpError as he:
        # If Google rejects threadId with 400 "Invalid thread_id value", retry cleanly without threadId
        if "thread" in str(he).lower():
            logger.warning(f"Gmail threadId rejected ({he}), retrying send without threadId")
            sent_resp = service.users().messages().send(userId="me", body={"raw": raw}).execute()
        else:
            raise
    except Exception as e:
        err_str = str(e).lower()
        if "invalid_grant" in err_str or "token has been expired" in err_str or "refresherror" in err_str:
            raise ValueError("Gmail authorization has expired or was revoked by Google. Please click 'Connect Gmail' in the dashboard to reconnect your account.")
        raise

    # If Gmail assigned a real threadId and messageId, update email_msg
    if sent_resp and sent_resp.get("threadId"):
        email_msg.gmail_thread_id = sent_resp["threadId"]


async def send_email_reply(
    db: AsyncSession,
    business_id: UUID,
    email_message_id: UUID,
    reply_body: Optional[str],
) -> EmailMessage:
    """
    Owner-triggered send from review mode with strict duplicate reply prevention,
    row-level concurrency locking, and uncertain-state reconciliation.
    """
    # 1. Acquire row-level lock on the incoming email to prevent race conditions
    result = await db.execute(
        select(EmailMessage)
        .where(
            EmailMessage.id == email_message_id,
            EmailMessage.business_id == business_id,
        )
        .with_for_update()
    )
    email_msg = result.scalar_one_or_none()
    if not email_msg:
        raise ValueError("Email message not found")

    # 2. Check if already replied to in database
    if email_msg.status == EmailMessageStatus.sent:
        raise ValueError("This email has already been replied to. Duplicate sending is not allowed.")

    # 3. Check if an outgoing reply record already exists for this incoming message
    existing_reply = await db.execute(
        select(EmailMessage).where(
            EmailMessage.related_message_id == email_msg.id,
            EmailMessage.direction == EmailMessageDirection.outgoing,
            EmailMessage.status == EmailMessageStatus.sent,
        )
    )
    if existing_reply.scalar_one_or_none():
        email_msg.status = EmailMessageStatus.sent
        await db.commit()
        raise ValueError("This email has already been replied to. Duplicate sending is not allowed.")

    body_to_send = reply_body or email_msg.draft_reply
    if not body_to_send or not body_to_send.strip():
        raise ValueError("No reply body provided")

    # 4. Get email account
    account_result = await db.execute(
        select(EmailAccount).where(EmailAccount.id == email_msg.email_account_id)
    )
    account = account_result.scalar_one_or_none()
    if not account:
        raise ValueError("Email account not found")

    # 5. Check provider type
    is_smtp_imap = False
    if account.encrypted_access_token:
        try:
            raw_creds = json.loads(decrypt_token(account.encrypted_access_token))
            if raw_creds.get("provider") == "smtp_imap":
                is_smtp_imap = True
        except Exception:
            pass

    # 6. Uncertain state reconciliation with Gmail:
    # If a prior send attempt succeeded at Gmail but crashed before DB commit,
    # reconcile DB status before blindly attempting another send.
    tid = email_msg.gmail_thread_id
    is_synthetic_tid = not tid or tid.startswith("thread-") or tid.startswith("sim-") or not all(c in "0123456789abcdefABCDEF" for c in tid)
    if not is_smtp_imap and not is_synthetic_tid:
        try:
            service, _ = _build_gmail_service(account)
            thread = service.users().threads().get(
                userId="me", id=email_msg.gmail_thread_id
            ).execute()
            messages = thread.get("messages", [])
            for m in messages:
                hdrs = {h.get("name", "").lower(): h.get("value", "") for h in m.get("payload", {}).get("headers", [])}
                in_reply = hdrs.get("in-reply-to", "")
                from_hdr = hdrs.get("from", "")
                if account.email_address.lower() in from_hdr.lower() and email_msg.gmail_message_id in in_reply:
                    # Gmail already contains the reply. Reconcile DB to sent.
                    email_msg.status = EmailMessageStatus.sent
                    email_msg.sent_at = datetime.now(timezone.utc)
                    await db.commit()
                    raise ValueError("This email has already been replied to. Duplicate sending is not allowed.")
        except ValueError:
            raise
        except Exception as te:
            logger.debug(f"Gmail thread reconciliation note: {te}")

    biz_result = await db.execute(
        select(Business).where(Business.id == business_id)
    )
    biz = biz_result.scalar_one()

    from app.email.email_processing import dispatch_email_reply
    await dispatch_email_reply(
        db=db,
        account=account,
        email_msg=email_msg,
        reply_body=body_to_send,
        business_name=biz.name,
    )

    await db.commit()
    await db.refresh(email_msg)
    return email_msg
