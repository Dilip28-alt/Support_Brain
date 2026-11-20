"""
Support Brain — Phases 10 & 11 Integration Tests: Email Integration & Gmail Pipeline
Tests:
  1. Gmail OAuth URL generation and scope verification.
  2. Review Mode: AI-generated drafts, owner review/edit, thread-preserving send,
     and duplicate reply prevention.
  3. Auto Mode: High-confidence automatic dispatch vs. low-confidence fallback to Pending Questions.
  4. Multi-Tenant Business Isolation across email accounts and messages.
"""
import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import AsyncSessionLocal
from app.models.models import (
    Business, User, EmailAccount, EmailMessage, KnowledgeSource,
    KnowledgeChunk, PendingQuestion, EmailProcessingMode,
    EmailAccountStatus, EmailMessageDirection, EmailMessageStatus,
    PendingQuestionSource, KnowledgeSourceType
)
from app.ai.gemini_client import get_embedding
from app.utils.auth import hash_password, create_access_token
from app.utils.encryption import encrypt_token
from app.email.email_processing import process_incoming_emails, format_reply_subject


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_phases_10_11_email_pipeline():
    uid = uuid.uuid4().hex[:6]
    biz_a_slug = f"acme-tech-{uid}"
    biz_b_slug = f"zenith-logistics-{uid}"

    # 1. Setup two businesses in Database
    async with AsyncSessionLocal() as session:
        # Business A: Acme Tech
        biz_a = Business(
            name="Acme Tech",
            slug=biz_a_slug,
            widget_token=f"sb_pub_acme_{uid}",
            is_active=True,
        )
        session.add(biz_a)
        await session.flush()

        user_a = User(
            business_id=biz_a.id,
            email=f"owner_{uid}@acme.com",
            full_name="Acme Owner",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        session.add(user_a)

        # Ingest knowledge for Acme Tech
        ks_a = KnowledgeSource(
            business_id=biz_a.id,
            title="Acme Warranty and Return Policy",
            source_type=KnowledgeSourceType.text,
            is_processed=True,
            chunk_count=1,
        )
        session.add(ks_a)
        await session.flush()

        kc_text = (
            "Acme Tech provides a 2-year full hardware replacement warranty on all servers. "
            "Defective components are replaced on-site within 24 hours of notification."
        )
        emb = get_embedding(kc_text, task_type="RETRIEVAL_DOCUMENT")
        kc = KnowledgeChunk(
            business_id=biz_a.id,
            source_id=ks_a.id,
            chunk_index=0,
            content=kc_text,
            embedding=emb,
            token_count=35,
        )
        session.add(kc)

        # Business B: Zenith Logistics
        biz_b = Business(
            name="Zenith Logistics",
            slug=biz_b_slug,
            widget_token=f"sb_pub_zenith_{uid}",
            is_active=True,
        )
        session.add(biz_b)
        await session.flush()

        user_b = User(
            business_id=biz_b.id,
            email=f"owner_{uid}@zenith.com",
            full_name="Zenith Owner",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        session.add(user_b)

        await session.commit()
        biz_a_id = biz_a.id
        biz_b_id = biz_b.id
        user_a_id = user_a.id
        user_b_id = user_b.id

    token_a = create_access_token({"sub": str(user_a_id)})
    token_b = create_access_token({"sub": str(user_b_id)})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # =================================================================
        # TEST 1: Gmail OAuth URL & Scope Verification
        # =================================================================
        resp_url = await client.get("/api/email/oauth/url", headers=headers_a)
        assert resp_url.status_code == 200
        auth_url = resp_url.json()["url"]
        assert "accounts.google.com" in auth_url
        assert "response_type=code" in auth_url
        assert "access_type=offline" in auth_url
        assert str(biz_a_id) in auth_url  # state contains business_id

        # =================================================================
        # TEST 2: Review Mode Flow (Draft Generation, Thread Preservation, Duplicate Prevention)
        # =================================================================
        async with AsyncSessionLocal() as session:
            # Connect Email Account in Review Mode
            acc_a = EmailAccount(
                business_id=biz_a_id,
                email_address=f"support@{biz_a_slug}.com",
                processing_mode=EmailProcessingMode.review,
                status=EmailAccountStatus.connected,
                encrypted_access_token=encrypt_token("mock-access-token"),
            )
            session.add(acc_a)
            await session.commit()
            acc_a_id = acc_a.id

        # Simulate incoming customer email to Acme Tech
        inquiry_subject = "Server Warranty inquiry"
        inquiry_body = "What is your hardware replacement warranty period for defective servers?"
        sim_res = await client.post("/api/email/simulate-incoming", json={
            "sender_name": "Bob Client",
            "sender_email": "bob@enterprise.org",
            "subject": inquiry_subject,
            "body": inquiry_body,
        }, headers=headers_a)
        assert sim_res.status_code == 200
        email_data = sim_res.json()
        email_id = email_data["id"]
        thread_id = email_data["gmail_thread_id"]

        # In Review Mode, status must be DRAFT and draft_reply must be generated from Knowledge
        assert email_data["status"] == "draft"
        assert email_data["draft_reply"] is not None
        assert "warranty" in email_data["draft_reply"].lower() or "2-year" in email_data["draft_reply"]

        # Owner edits the draft
        updated_draft = "Hello Bob,\n\nWe provide a 2-year full hardware replacement warranty with 24-hour on-site dispatch.\n\nBest,\nAcme Support"
        patch_draft_res = await client.patch(
            f"/api/email/messages/{email_id}/draft",
            json={"draft_reply": updated_draft},
            headers=headers_a
        )
        assert patch_draft_res.status_code == 200
        assert patch_draft_res.json()["draft_reply"] == updated_draft

        # Owner clicks Send Reply (Mocking out external network call to Gmail API)
        import unittest.mock as mock
        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock.MagicMock(), None)), \
             mock.patch("app.email.gmail_service._send_reply", new_callable=mock.AsyncMock) as mock_send:
            send_res = await client.post("/api/email/messages/send", json={
                "email_message_id": email_id,
                "reply_body": updated_draft,
            }, headers=headers_a)
            assert send_res.status_code == 200
            assert send_res.json()["status"] == "sent"

        # Verify thread preservation and outbound message record
        async with AsyncSessionLocal() as session:
            out_res = await session.execute(
                select(EmailMessage).where(
                    EmailMessage.business_id == biz_a_id,
                    EmailMessage.direction == EmailMessageDirection.outgoing,
                    EmailMessage.gmail_thread_id == thread_id,
                )
            )
            out_msg = out_res.scalar_one_or_none()
            assert out_msg is not None
            assert out_msg.recipient == "Bob Client <bob@enterprise.org>"
            assert out_msg.subject == format_reply_subject(inquiry_subject)
            assert out_msg.status == EmailMessageStatus.sent

        # Duplicate Prevention Check:
        # Attempting to send a second reply to the same email message must be rejected!
        dup_res = await client.post("/api/email/messages/send", json={
            "email_message_id": email_id,
            "reply_body": "Sending again by mistake",
        }, headers=headers_a)
        assert dup_res.status_code == 400
        assert "already" in dup_res.json()["detail"].lower()

        # =================================================================
        # TEST 3: Auto Mode Flow (Auto-Send for High Confidence, Pending for Low Confidence)
        # =================================================================
        # Switch account to Auto Mode
        mode_res = await client.patch(
            f"/api/email/accounts/{acc_a_id}",
            json={"processing_mode": "auto"},
            headers=headers_a
        )
        assert mode_res.status_code == 200
        assert mode_res.json()["processing_mode"] == "auto"

        # Case A: High Confidence Inquiry (Auto-Sent)
        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock.MagicMock(), None)), \
             mock.patch("app.email.gmail_service._send_reply", new_callable=mock.AsyncMock) as mock_send_auto:
            sim_auto_res = await client.post("/api/email/simulate-incoming", json={
                "sender_name": "Charlie Corporate",
                "sender_email": "charlie@corp.com",
                "subject": "Hardware Warranty Duration",
                "body": "What is the warranty period for defective servers?",
            }, headers=headers_a)
            assert sim_auto_res.status_code == 200
            auto_data = sim_auto_res.json()
            # Must be auto-sent!
            assert auto_data["status"] == "sent"
            assert auto_data["sent_at"] is not None

        # Case B: Low Confidence / Unknown Inquiry (Must NOT send; must queue to Pending)
        sim_low_res = await client.post("/api/email/simulate-incoming", json={
            "sender_name": "Dave Curious",
            "sender_email": "dave@curious.com",
            "subject": "Quantum teleportation question",
            "body": "Does Acme Tech provide quantum entanglement teleporters?",
        }, headers=headers_a)
        assert sim_low_res.status_code == 200
        low_data = sim_low_res.json()
        low_id = low_data["id"]

        # Must NOT auto-send ungrounded hallucination!
        assert low_data["status"] == "draft"

        # Verify queued in Pending Questions table with source EMAIL
        async with AsyncSessionLocal() as session:
            pq_res = await session.execute(
                select(PendingQuestion).where(
                    PendingQuestion.business_id == biz_a_id,
                    PendingQuestion.source == PendingQuestionSource.email,
                    PendingQuestion.email_message_id == low_id,
                )
            )
            pq = pq_res.scalar_one_or_none()
            assert pq is not None
            assert "quantum entanglement" in pq.customer_question

        # =================================================================
        # TEST 4: Multi-Tenant Email Isolation
        # =================================================================
        # Business B must NOT see Business A's accounts or email messages
        b_accs_res = await client.get("/api/email/accounts", headers=headers_b)
        assert b_accs_res.status_code == 200
        assert len(b_accs_res.json()) == 0

        b_msgs_res = await client.get("/api/email/messages", headers=headers_b)
        assert b_msgs_res.status_code == 200
        assert len(b_msgs_res.json()) == 0
