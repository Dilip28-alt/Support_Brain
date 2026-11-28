"""
SMTP and IMAP email integration service.
Handles connecting custom inbox servers, fetching unread emails, and sending replies.
"""
from typing import Optional, List, Tuple
from uuid import UUID
import uuid
from datetime import datetime, timezone
import imaplib
import smtplib
import email
from email.header import decode_header
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.models.models import (
    EmailAccount, EmailMessage, EmailAccountStatus,
    EmailMessageDirection, EmailMessageStatus,
    PendingQuestion, PendingQuestionSource, Business,
    EmailProcessingMode, Lesson
)
from app.ai.gemini_client import generate_email_reply, compute_confidence_score
from app.ai.search import search_knowledge, search_lessons
from app.utils.encryption import encrypt_token, decrypt_token
from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


def _decode_str(s) -> str:
    """Decode encoded email header string."""
    if not s:
        return ""
    decoded_fragments = decode_header(s)
    result = []
    for fragment, encoding in decoded_fragments:
        if isinstance(fragment, bytes):
            result.append(fragment.decode(encoding or "utf-8", errors="replace"))
        else:
            result.append(str(fragment))
    return "".join(result)


def test_smtp_imap_connection(
    email_address: str,
    imap_host: str,
    imap_port: int,
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
) -> Tuple[bool, str]:
    """Test IMAP and SMTP credentials synchronously."""
    # Test IMAP
    try:
        if imap_port == 993:
            imap = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=10)
        else:
            imap = imaplib.IMAP4(imap_host, imap_port, timeout=10)
        imap.login(username, password)
        imap.logout()
    except Exception as e:
        return False, f"IMAP connection failed ({imap_host}:{imap_port}): {str(e)}"

    # Test SMTP
    try:
        if smtp_port == 465:
            smtp = smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=10)
        else:
            smtp = smtplib.SMTP(smtp_host, smtp_port, timeout=10)
            smtp.starttls()
        smtp.login(username, password)
        smtp.quit()
    except Exception as e:
        return False, f"SMTP connection failed ({smtp_host}:{smtp_port}): {str(e)}"

    return True, "Connection successful"


async def connect_smtp_imap_account(
    db: AsyncSession,
    business_id: UUID,
    email_address: str,
    imap_host: str,
    imap_port: int,
    smtp_host: str,
    smtp_port: int,
    username: str,
    password: str,
    processing_mode: EmailProcessingMode = EmailProcessingMode.review,
) -> EmailAccount:
    """Save or update an SMTP/IMAP email account with encrypted credentials."""
    creds_payload = {
        "provider": "smtp_imap",
        "imap_host": imap_host,
        "imap_port": imap_port,
        "smtp_host": smtp_host,
        "smtp_port": smtp_port,
        "username": username,
        "password": password,
    }
    encrypted_blob = encrypt_token(json.dumps(creds_payload))

    result = await db.execute(
        select(EmailAccount).where(
            EmailAccount.business_id == business_id,
            EmailAccount.email_address == email_address,
        )
    )
    account = result.scalar_one_or_none()

    if account:
        account.encrypted_access_token = encrypted_blob
        account.processing_mode = processing_mode
        account.status = EmailAccountStatus.connected
    else:
        account = EmailAccount(
            business_id=business_id,
            email_address=email_address,
            encrypted_access_token=encrypted_blob,
            processing_mode=processing_mode,
            status=EmailAccountStatus.connected,
        )
        db.add(account)

    await db.commit()
    await db.refresh(account)
    return account


def _get_smtp_imap_creds(account: EmailAccount) -> dict:
    """Decrypt credentials from account."""
    if not account.encrypted_access_token:
        raise ValueError("No credentials stored for this account")
    decrypted = decrypt_token(account.encrypted_access_token)
    try:
        return json.loads(decrypted)
    except Exception:
        raise ValueError("Invalid credentials payload")


def send_smtp_message(
    account: EmailAccount,
    to_email: str,
    subject: str,
    body: str,
    in_reply_to: Optional[str] = None,
    references: Optional[str] = None,
) -> None:
    """Send an email using SMTP."""
    creds = _get_smtp_imap_creds(account)
    smtp_host = creds.get("smtp_host")
    smtp_port = int(creds.get("smtp_port", 587))
    username = creds.get("username")
    password = creds.get("password")

    msg = MIMEMultipart("alternative")
    msg["From"] = account.email_address
    msg["To"] = to_email
    msg["Subject"] = subject
    if in_reply_to:
        msg["In-Reply-To"] = in_reply_to
    if references:
        msg["References"] = references

    msg.attach(MIMEText(body, "plain", "utf-8"))

    if smtp_port == 465:
        with smtplib.SMTP_SSL(smtp_host, smtp_port, timeout=15) as server:
            server.login(username, password)
            server.sendmail(account.email_address, [to_email], msg.as_string())
    else:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=15) as server:
            server.starttls()
            server.login(username, password)
            server.sendmail(account.email_address, [to_email], msg.as_string())


async def fetch_imap_new_emails(
    db: AsyncSession,
    account: EmailAccount,
    business: Business,
) -> List[EmailMessage]:
    """Poll IMAP server for unread incoming emails."""
    try:
        creds = _get_smtp_imap_creds(account)
    except Exception as e:
        logger.error(f"Cannot read SMTP/IMAP credentials: {e}")
        return []

    imap_host = creds.get("imap_host")
    imap_port = int(creds.get("imap_port", 993))
    username = creds.get("username")
    password = creds.get("password")

    new_messages: List[EmailMessage] = []

    try:
        if imap_port == 993:
            mail = imaplib.IMAP4_SSL(imap_host, imap_port, timeout=15)
        else:
            mail = imaplib.IMAP4(imap_host, imap_port, timeout=15)
        mail.login(username, password)
        mail.select("INBOX")

        status, response = mail.search(None, "UNSEEN")
        if status != "OK":
            mail.logout()
            return []

        msg_ids = response[0].split()
        for num in msg_ids[-20:]:  # check last 20 unread
            res, data = mail.fetch(num, "(RFC822)")
            if res != "OK" or not data:
                continue

            raw_email = data[0][1]
            msg = email.message_from_bytes(raw_email)

            message_id = msg.get("Message-ID") or f"imap-{uuid.uuid4().hex[:16]}"
            # Idempotency check: skip if already saved
            existing = await db.execute(
                select(EmailMessage).where(EmailMessage.gmail_message_id == message_id)
            )
            if existing.scalar_one_or_none():
                continue

            subject = _decode_str(msg.get("Subject")) or "(no subject)"
            sender = _decode_str(msg.get("From")) or ""
            recipient = _decode_str(msg.get("To")) or account.email_address
            thread_id = msg.get("In-Reply-To") or message_id

            # Extract body
            body_text = ""
            body_html = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ctype = part.get_content_type()
                    cdisp = str(part.get("Content-Disposition"))
                    if "attachment" in cdisp:
                        continue
                    payload = part.get_payload(decode=True)
                    if not payload:
                        continue
                    if ctype == "text/plain" and not body_text:
                        body_text = payload.decode(errors="replace")
                    elif ctype == "text/html" and not body_html:
                        body_html = payload.decode(errors="replace")
            else:
                ctype = msg.get_content_type()
                payload = msg.get_payload(decode=True)
                if payload:
                    decoded = payload.decode(errors="replace")
                    if ctype == "text/html":
                        body_html = decoded
                    else:
                        body_text = decoded

            from app.utils.html_utils import extract_readable_email_text
            clean_body = extract_readable_email_text(body_text=body_text, body_html=body_html, subject=subject)

            email_msg = EmailMessage(
                business_id=account.business_id,
                email_account_id=account.id,
                gmail_message_id=message_id,
                gmail_thread_id=thread_id,
                direction=EmailMessageDirection.incoming,
                subject=subject,
                sender=sender,
                recipient=recipient,
                body_text=clean_body,
                body_html=body_html.strip(),
                status=EmailMessageStatus.pending,
                received_at=datetime.now(timezone.utc),
            )
            db.add(email_msg)
            new_messages.append(email_msg)

        mail.logout()
    except Exception as e:
        logger.error(f"IMAP fetch failed for {account.email_address}: {e}")
        return []

    if new_messages:
        await db.flush()
        # Generate drafts from Brain
        from app.email.email_processing import process_incoming_emails
        await process_incoming_emails(db, new_messages, business, account)

    await db.commit()
    return new_messages
