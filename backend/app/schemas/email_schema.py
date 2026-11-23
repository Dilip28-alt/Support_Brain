"""
Pydantic schemas for Email integration.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
from datetime import datetime
from app.models.models import EmailProcessingMode, EmailMessageStatus


class EmailAccountResponse(BaseModel):
    id: UUID
    business_id: UUID
    email_address: str
    processing_mode: EmailProcessingMode
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class EmailAccountUpdate(BaseModel):
    processing_mode: EmailProcessingMode


class SmtpImapConnectRequest(BaseModel):
    email_address: str
    imap_host: str
    imap_port: int = 993
    smtp_host: str
    smtp_port: int = 587
    username: str
    password: str
    processing_mode: EmailProcessingMode = EmailProcessingMode.review


class SimulateIncomingEmailRequest(BaseModel):
    sender_email: str = Field(..., description="Customer's email address")
    sender_name: Optional[str] = "Customer"
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email question or inquiry body")


class ComposeEmailRequest(BaseModel):
    recipient: str = Field(..., description="Recipient email address")
    subject: str = Field(..., description="Email subject")
    body: str = Field(..., description="Email body content")


class EmailMessageResponse(BaseModel):
    id: UUID
    business_id: UUID
    email_account_id: UUID
    gmail_message_id: str
    gmail_thread_id: str
    direction: str
    subject: Optional[str]
    sender: Optional[str]
    recipient: Optional[str]
    body_text: Optional[str]
    draft_reply: Optional[str]
    status: EmailMessageStatus
    related_message_id: Optional[UUID] = None
    received_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True


class EmailSendRequest(BaseModel):
    email_message_id: UUID
    reply_body: Optional[str] = None   # if None, use draft_reply


class EmailDraftUpdate(BaseModel):
    email_message_id: Optional[UUID] = None
    draft_reply: str
