"""
Support Brain — Email Safety, Duplicate Reply Prevention, and History Tests

Scenarios Covered:
  Test 1: Incoming email is saved once even when Gmail polling fetches it repeatedly (Idempotency).
  Test 2: Incoming email creates a Review Mode draft without auto-dispatching.
  Test 3: First Send attempt successfully sends and records the outgoing email.
  Test 4: Second Send attempt for the same incoming email is rejected with clear error.
  Test 5: Two simultaneous Send attempts cannot produce duplicate replies (Concurrency safety).
  Test 6: Incoming and outgoing emails both appear in email history with complete metadata.
  Test 7: Email history is strictly isolated between two different businesses.
  Test 8: A failed or uncertain Gmail send reconciles state safely without duplicate sending.
"""
import pytest
import asyncio
import uuid
import unittest.mock as mock
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import AsyncSessionLocal
from app.models.models import (
    Business, User, EmailAccount, EmailMessage, KnowledgeSource,
    KnowledgeChunk, EmailProcessingMode, EmailAccountStatus,
    EmailMessageDirection, EmailMessageStatus, KnowledgeSourceType
)
from app.ai.gemini_client import get_embedding
from app.utils.auth import hash_password, create_access_token
from app.utils.encryption import encrypt_token
from app.email.gmail_service import fetch_new_emails, send_email_reply
from app.email.email_processing import format_reply_subject


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_email_safety_full_suite():
    uid = uuid.uuid4().hex[:6]
    biz_a_slug = f"alpha-corp-{uid}"
    biz_b_slug = f"beta-retail-{uid}"

    # ─────────────────────────────────────────────────────────────
    # Database Setup: Two Independent Businesses (Alpha and Beta)
    # ─────────────────────────────────────────────────────────────
    async with AsyncSessionLocal() as session:
        biz_a = Business(
            name="Alpha Corp",
            slug=biz_a_slug,
            widget_token=f"sb_pub_alpha_{uid}",
            is_active=True,
        )
        session.add(biz_a)
        await session.flush()

        user_a = User(
            business_id=biz_a.id,
            email=f"owner_{uid}@alpha.com",
            full_name="Alpha Owner",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        session.add(user_a)

        # Knowledge for Alpha Corp
        ks_a = KnowledgeSource(
            business_id=biz_a.id,
            title="Alpha Return and Refund Policy",
            source_type=KnowledgeSourceType.text,
            is_processed=True,
            chunk_count=1,
        )
        session.add(ks_a)
        await session.flush()

        kc_text = "Alpha Corp provides a 30-day money-back refund guarantee on all products."
        emb = get_embedding(kc_text, task_type="RETRIEVAL_DOCUMENT")
        session.add(KnowledgeChunk(
            business_id=biz_a.id,
            source_id=ks_a.id,
            chunk_index=0,
            content=kc_text,
            embedding=emb,
            token_count=15,
        ))

        # Email account for Alpha Corp in Review Mode
        acc_a = EmailAccount(
            business_id=biz_a.id,
            email_address=f"support@{biz_a_slug}.com",
            encrypted_access_token=encrypt_token("mock-access-token-a"),
            encrypted_refresh_token=encrypt_token("mock-refresh-token-a"),
            token_expiry=datetime.now(timezone.utc),
            processing_mode=EmailProcessingMode.review,
            status=EmailAccountStatus.connected,
        )
        session.add(acc_a)

        # Business B: Beta Retail
        biz_b = Business(
            name="Beta Retail",
            slug=biz_b_slug,
            widget_token=f"sb_pub_beta_{uid}",
            is_active=True,
        )
        session.add(biz_b)
        await session.flush()

        user_b = User(
            business_id=biz_b.id,
            email=f"owner_{uid}@beta.com",
            full_name="Beta Owner",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        session.add(user_b)

        acc_b = EmailAccount(
            business_id=biz_b.id,
            email_address=f"help@{biz_b_slug}.com",
            encrypted_access_token=encrypt_token("mock-access-token-b"),
            encrypted_refresh_token=encrypt_token("mock-refresh-token-b"),
            token_expiry=datetime.now(timezone.utc),
            processing_mode=EmailProcessingMode.review,
            status=EmailAccountStatus.connected,
        )
        session.add(acc_b)

        await session.commit()
        biz_a_id = biz_a.id
        biz_b_id = biz_b.id
        user_a_id = user_a.id
        user_b_id = user_b.id
        acc_a_id = acc_a.id
        acc_b_id = acc_b.id

    token_a = create_access_token({"sub": str(user_a_id)})
    token_b = create_access_token({"sub": str(user_b_id)})
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:

        # ─────────────────────────────────────────────────────────────
        # TEST 1: Polling Idempotency
        # Incoming email is saved once even when Gmail polling fetches it repeatedly
        # ─────────────────────────────────────────────────────────────
        mock_gmail_msg_id = f"gmail_msg_{uid}_001"
        mock_thread_id = f"gmail_thread_{uid}_001"

        mock_raw_msg = {
            "id": mock_gmail_msg_id,
            "threadId": mock_thread_id,
            "internalDate": "1700000000000",
            "payload": {
                "headers": [
                    {"name": "Subject", "value": "Question on Return Window"},
                    {"name": "From", "value": "Customer One <customer1@example.com>"},
                    {"name": "To", "value": f"support@{biz_a_slug}.com"},
                ],
                "body": {"data": ""},
                "parts": [
                    {
                        "mimeType": "text/plain",
                        "body": {"data": "SG93IG1hbnkgZGF5cyBkbyBJIGhhdmUgdG8gcmV0dXJuIGEgcHVyY2hhc2U/"},  # "How many days do I have to return a purchase?"
                    }
                ],
            },
        }

        mock_service = mock.MagicMock()
        mock_service.users().messages().list().execute.return_value = {
            "messages": [{"id": mock_gmail_msg_id}]
        }
        mock_service.users().messages().get().execute.return_value = mock_raw_msg

        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock_service, None)):
            async with AsyncSessionLocal() as session:
                acc_obj = await session.get(EmailAccount, acc_a_id)
                biz_obj = await session.get(Business, biz_a_id)

                # Poll #1: should insert 1 email
                res_1 = await fetch_new_emails(session, acc_obj, biz_obj)
                assert len(res_1) == 1

                # Poll #2: same message returned by Gmail API, must skip insertion
                res_2 = await fetch_new_emails(session, acc_obj, biz_obj)
                assert len(res_2) == 0

            # Verify database has strictly 1 record
            async with AsyncSessionLocal() as session:
                count_res = await session.execute(
                    select(EmailMessage).where(EmailMessage.gmail_message_id == mock_gmail_msg_id)
                )
                records = count_res.scalars().all()
                assert len(records) == 1
                incoming_email = records[0]
                incoming_id = incoming_email.id

        # ─────────────────────────────────────────────────────────────
        # TEST 2: Review Mode Draft Generation
        # Incoming email creates a Review Mode draft without auto-sending
        # ─────────────────────────────────────────────────────────────
        sim_res = await client.post("/api/email/simulate-incoming", json={
            "sender_name": "Alice Customer",
            "sender_email": "alice@customer.com",
            "subject": "Do you offer refunds?",
            "body": "What is your refund guarantee window?",
        }, headers=headers_a)
        assert sim_res.status_code == 200
        sim_data = sim_res.json()
        sim_email_id = sim_data["id"]

        # In Review Mode, status MUST be draft
        assert sim_data["status"] == "draft"
        assert sim_data["draft_reply"] is not None
        assert "30-day" in sim_data["draft_reply"] or "refund" in sim_data["draft_reply"].lower()

        # ─────────────────────────────────────────────────────────────
        # TEST 3: First Send Attempt (Review Mode Dispatch)
        # First Send attempt successfully sends and records the outgoing email
        # ─────────────────────────────────────────────────────────────
        approved_reply = "Hello Alice,\n\nWe provide a 30-day money-back refund guarantee on all products.\n\nBest,\nAlpha Team"

        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock.MagicMock(), None)), \
             mock.patch("app.email.gmail_service._send_reply", new_callable=mock.AsyncMock) as mock_send_api:
            send_res = await client.post("/api/email/messages/send", json={
                "email_message_id": sim_email_id,
                "reply_body": approved_reply,
            }, headers=headers_a)
            assert send_res.status_code == 200
            assert send_res.json()["status"] == "sent"
            assert send_res.json()["sent_at"] is not None
            mock_send_api.assert_called_once()

        # Verify outgoing email message record created in database with related_message_id
        async with AsyncSessionLocal() as session:
            out_res = await session.execute(
                select(EmailMessage).where(
                    EmailMessage.related_message_id == sim_email_id,
                    EmailMessage.direction == EmailMessageDirection.outgoing,
                )
            )
            out_msg = out_res.scalar_one_or_none()
            assert out_msg is not None
            assert out_msg.status == EmailMessageStatus.sent
            assert out_msg.body_text == approved_reply
            assert out_msg.recipient == "Alice Customer <alice@customer.com>"
            assert out_msg.subject == "Re: Do you offer refunds?"

        # ─────────────────────────────────────────────────────────────
        # TEST 4: Second Send Attempt Rejected
        # Second Send attempt for the same incoming email is rejected
        # ─────────────────────────────────────────────────────────────
        dup_res = await client.post("/api/email/messages/send", json={
            "email_message_id": sim_email_id,
            "reply_body": "Attempting second reply",
        }, headers=headers_a)
        assert dup_res.status_code == 400
        assert "already been replied to" in dup_res.json()["detail"]

        # ─────────────────────────────────────────────────────────────
        # TEST 5: Simultaneous Send Concurrency Protection
        # Two simultaneous Send requests cannot produce duplicate replies
        # ─────────────────────────────────────────────────────────────
        sim2_res = await client.post("/api/email/simulate-incoming", json={
            "sender_name": "Bob Concurrent",
            "sender_email": "bob@concurrent.com",
            "subject": "Concurrency test inquiry",
            "body": "Can I return products within 30 days?",
        }, headers=headers_a)
        assert sim2_res.status_code == 200
        sim2_id = sim2_res.json()["id"]

        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock.MagicMock(), None)), \
             mock.patch("app.email.gmail_service._send_reply", new_callable=mock.AsyncMock):
            # Fire 2 send requests concurrently
            req1 = client.post("/api/email/messages/send", json={
                "email_message_id": sim2_id,
                "reply_body": "Concurrent reply attempt 1",
            }, headers=headers_a)
            req2 = client.post("/api/email/messages/send", json={
                "email_message_id": sim2_id,
                "reply_body": "Concurrent reply attempt 2",
            }, headers=headers_a)

            results = await asyncio.gather(req1, req2, return_exceptions=True)
            status_codes = [r.status_code for r in results if not isinstance(r, Exception)]

            # Exactly one request must succeed (200) and the duplicate must be rejected (400)
            assert 200 in status_codes
            assert 400 in status_codes

        # Verify exactly 1 outgoing reply exists in the database
        async with AsyncSessionLocal() as session:
            out2_res = await session.execute(
                select(EmailMessage).where(
                    EmailMessage.related_message_id == sim2_id,
                    EmailMessage.direction == EmailMessageDirection.outgoing,
                )
            )
            out2_msgs = out2_res.scalars().all()
            assert len(out2_msgs) == 1

        # ─────────────────────────────────────────────────────────────
        # TEST 6: Email History Complete Metadata
        # Both incoming and outgoing emails appear in history with all fields
        # ─────────────────────────────────────────────────────────────
        hist_res = await client.get("/api/email/messages", headers=headers_a)
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) >= 2

        # Check presence of incoming and outgoing records with full metadata
        directions = {item["direction"] for item in history}
        assert "incoming" in directions
        assert "outgoing" in directions

        sample_incoming = next(item for item in history if item["direction"] == "incoming")
        assert sample_incoming["business_id"] == str(biz_a_id)
        assert sample_incoming["gmail_message_id"] is not None
        assert sample_incoming["gmail_thread_id"] is not None
        assert sample_incoming["sender"] is not None
        assert sample_incoming["recipient"] is not None
        assert sample_incoming["status"] in ["draft", "sent", "pending"]

        sample_outgoing = next(item for item in history if item["direction"] == "outgoing")
        assert sample_outgoing["business_id"] == str(biz_a_id)
        assert sample_outgoing["related_message_id"] is not None
        assert sample_outgoing["status"] == "sent"

        # ─────────────────────────────────────────────────────────────
        # TEST 7: Business Isolation
        # Email history is isolated between two different businesses
        # ─────────────────────────────────────────────────────────────
        # Business B queries its email messages
        hist_b_res = await client.get("/api/email/messages", headers=headers_b)
        assert hist_b_res.status_code == 200
        history_b = hist_b_res.json()

        # Business B should have 0 messages from Business A
        biz_a_str = str(biz_a_id)
        for msg in history_b:
            assert msg["business_id"] != biz_a_str

        # ─────────────────────────────────────────────────────────────
        # TEST 8: Uncertain Gmail Send State Recovery (Reconciliation)
        # If Gmail already contains the reply in the thread, reconcile DB safely without duplicate send
        # ─────────────────────────────────────────────────────────────
        sim3_res = await client.post("/api/email/simulate-incoming", json={
            "sender_name": "Charlie Uncertain",
            "sender_email": "charlie@uncertain.com",
            "subject": "Uncertain state test",
            "body": "What is the return period?",
        }, headers=headers_a)
        assert sim3_res.status_code == 200
        sim3_data = sim3_res.json()
        sim3_id = sim3_data["id"]
        sim3_msg_id = sim3_data["gmail_message_id"]
        sim3_thread_id = sim3_data["gmail_thread_id"]

        # Simulate scenario: Gmail thread already contains a sent reply from our support email
        # (e.g. earlier send succeeded at Google API, but network dropped before DB updated status)
        mock_thread_with_reply = {
            "id": sim3_thread_id,
            "messages": [
                {
                    "id": sim3_msg_id,
                    "payload": {
                        "headers": [
                            {"name": "from", "value": "charlie@uncertain.com"},
                            {"name": "in-reply-to", "value": ""},
                        ]
                    }
                },
                {
                    "id": f"already_sent_{uid}",
                    "payload": {
                        "headers": [
                            {"name": "from", "value": f"support@{biz_a_slug}.com"},
                            {"name": "in-reply-to", "value": sim3_msg_id},
                        ]
                    }
                }
            ]
        }

        mock_svc_uncertain = mock.MagicMock()
        mock_svc_uncertain.users().threads().get().execute.return_value = mock_thread_with_reply

        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock_svc_uncertain, None)), \
             mock.patch("app.email.gmail_service._send_reply", new_callable=mock.AsyncMock) as mock_send_unsafe:
            
            # Send attempt must detect that Gmail already sent the reply, reconcile DB, and reject second send
            uncertain_res = await client.post("/api/email/messages/send", json={
                "email_message_id": sim3_id,
                "reply_body": "Trying to send again after uncertain state",
            }, headers=headers_a)

            assert uncertain_res.status_code == 400
            assert "already been replied to" in uncertain_res.json()["detail"]
            # Crucial: Unsafe duplicate Gmail send was ABORTED
            mock_send_unsafe.assert_not_called()

        # Database must now be reconciled to status = 'sent'
        async with AsyncSessionLocal() as session:
            chk_msg = await session.get(EmailMessage, sim3_id)
            assert chk_msg.status == EmailMessageStatus.sent

        # ─────────────────────────────────────────────────────────────
        # TEST 9: Public Customer Email Inquiry from Chat Link
        # Customer asks a question through email on the public chat link
        # ─────────────────────────────────────────────────────────────
        pub_inquiry_res = await client.post("/api/chat/public/email-inquiry", json={
            "business_slug": biz_a_slug,
            "sender_name": "Public Visitor",
            "sender_email": "visitor@publicweb.com",
            "subject": "Inquiry about refund guarantee",
            "message": "Hello, how many days do I have to return an item under your guarantee?",
        })
        assert pub_inquiry_res.status_code == 200
        pub_data = pub_inquiry_res.json()
        assert pub_data["status"] == "success"
        pub_email_id = pub_data["email_id"]

        # Verify the inquiry is saved in Business A's email records with AI draft ready for review
        async with AsyncSessionLocal() as session:
            pub_chk = await session.get(EmailMessage, pub_email_id)
            assert pub_chk is not None
            assert pub_chk.business_id == biz_a_id
            assert pub_chk.direction == EmailMessageDirection.incoming
            assert "visitor@publicweb.com" in pub_chk.sender
            assert pub_chk.draft_reply is not None
            assert len(pub_chk.draft_reply) > 0
