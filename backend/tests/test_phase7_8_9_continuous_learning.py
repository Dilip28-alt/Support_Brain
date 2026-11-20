"""
Support Brain — Phases 7, 8, & 9 Integration Tests
Covers:
  Phase 7: Pending Questions, Owner Responses, and Add Answer to Brain.
  Phase 8: Good/Bad Answer Feedback, Automatic Lesson Creation, and Lessons Management.
  Phase 9: Ask This Question Again (side-by-side comparison), demonstration that
           corrected answers are retrieved for future similar questions, and
           strict multi-tenant business isolation.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import AsyncSessionLocal
from app.models.models import (
    Business, User, PendingQuestion, Lesson, Message,
    Conversation, AnswerFeedback, PendingQuestionStatus, MessageRole
)
from app.utils.auth import hash_password, create_access_token


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_phases_7_8_9_continuous_learning_and_isolation():
    uid = uuid.uuid4().hex[:6]
    biz_a_slug = f"nexora-software-{uid}"
    biz_b_slug = f"solaria-solar-{uid}"
    biz_a_token = f"sb_pub_nexora_{uid}"
    biz_b_token = f"sb_pub_solaria_{uid}"

    # 1. Setup two businesses in Database
    async with AsyncSessionLocal() as session:
        # Business A: Nexora Software
        biz_a = Business(
            name="Nexora Software",
            slug=biz_a_slug,
            widget_token=biz_a_token,
            is_active=True,
        )
        session.add(biz_a)
        await session.flush()

        user_a = User(
            business_id=biz_a.id,
            email=f"owner_{uid}@nexora.com",
            full_name="Nexora Admin",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        session.add(user_a)

        # Business B: Solaria Solar
        biz_b = Business(
            name="Solaria Solar",
            slug=biz_b_slug,
            widget_token=biz_b_token,
            is_active=True,
        )
        session.add(biz_b)
        await session.flush()

        user_b = User(
            business_id=biz_b.id,
            email=f"owner_{uid}@solaria.com",
            full_name="Solaria Admin",
            hashed_password=hash_password("Password123!"),
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
        # PHASE 7: Pending Questions & Add Answer to Brain
        # =================================================================

        # Step 1: Customer asks Nexora an ungrounded question via public chat
        sso_question = "Do you support Single Sign-On (SSO) via SAML 2.0 or OIDC?"
        chat_req = {
            "business_token": biz_a_token,
            "question": sso_question,
            "customer_name": "Alice Customer",
            "customer_email": "alice@acme.corp",
        }
        chat_res = await client.post("/api/chat", json=chat_req)
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert chat_data["is_pending"] is True
        assert chat_data["answer"] == "Thank you! The team will reply to you soon."
        conversation_id = chat_data["conversation_id"]

        # Step 2: Nexora owner views Pending Questions
        pending_res_a = await client.get("/api/pending/?status_filter=open", headers=headers_a)
        assert pending_res_a.status_code == 200
        pending_list_a = pending_res_a.json()
        assert len(pending_list_a) >= 1
        target_pending = next(p for p in pending_list_a if p["customer_question"] == sso_question)
        assert target_pending["customer_name"] == "Alice Customer"
        assert target_pending["customer_email"] == "alice@acme.corp"
        pending_id = target_pending["id"]

        # Step 3: Verify Business Isolation on Pending Questions
        # Solaria Solar's owner must NOT see Nexora's pending question
        pending_res_b = await client.get("/api/pending/?status_filter=open", headers=headers_b)
        assert pending_res_b.status_code == 200
        pending_list_b = pending_res_b.json()
        assert not any(p["customer_question"] == sso_question for p in pending_list_b)

        # Step 4: Nexora owner answers question and clicks "Add this answer to the Brain"
        sso_owner_answer = "Nexora supports enterprise SSO with SAML 2.0 and OIDC on all Business and Enterprise plans."
        resolve_payload = {
            "owner_answer": sso_owner_answer,
            "add_to_brain": True,
            "send_via_channel": True,
        }
        resolve_res = await client.post(f"/api/pending/{pending_id}/resolve", json=resolve_payload, headers=headers_a)
        assert resolve_res.status_code == 200
        assert resolve_res.json()["status"] == "resolved"

        # Verify question is marked resolved and a lesson was created
        async with AsyncSessionLocal() as session:
            lesson_res = await session.execute(
                select(Lesson).where(
                    Lesson.business_id == biz_a_id,
                    Lesson.question == sso_question,
                )
            )
            created_lesson = lesson_res.scalar_one_or_none()
            assert created_lesson is not None
            assert created_lesson.corrected_answer == sso_owner_answer
            assert created_lesson.is_active is True
            assert created_lesson.embedding is not None

        # =================================================================
        # PHASE 8: Good/Bad Feedback & Lessons Management
        # =================================================================

        # Step 1: Customer asks about data export
        export_q = "How often do you export database backups?"
        chat_req_2 = {
            "business_token": biz_a_token,
            "question": export_q,
            "conversation_id": conversation_id,
        }
        chat_res_2 = await client.post("/api/chat", json=chat_req_2)
        assert chat_res_2.status_code == 200
        message_id_2 = chat_res_2.json()["message_id"]

        # Step 2: Owner marks Bad answer and teaches the AI
        export_correct_answer = "Nexora exports automated database backups every 60 minutes with 90-day retention."
        feedback_payload = {
            "message_id": message_id_2,
            "conversation_id": conversation_id,
            "feedback_type": "bad",
            "question": export_q,
            "correct_answer": export_correct_answer,
            "owner_comment": "Official backup policy Q1 2026",
        }
        fb_res = await client.post("/api/feedback", json=feedback_payload, headers=headers_a)
        assert fb_res.status_code == 201
        assert fb_res.json()["lesson_created"] is True
        lesson_id_export = fb_res.json()["lesson_id"]

        # Step 3: Lessons Management API
        # List lessons for Nexora
        lessons_res_a = await client.get("/api/lessons/", headers=headers_a)
        assert lessons_res_a.status_code == 200
        lessons_a = lessons_res_a.json()
        assert len(lessons_a) >= 2  # SSO lesson + export lesson

        # Solaria Solar lessons list must be empty / isolated
        lessons_res_b = await client.get("/api/lessons/", headers=headers_b)
        assert lessons_res_b.status_code == 200
        lessons_b = lessons_res_b.json()
        assert len(lessons_b) == 0

        # Toggle lesson inactive then active
        patch_res = await client.patch(f"/api/lessons/{lesson_id_export}", json={"is_active": False}, headers=headers_a)
        assert patch_res.status_code == 200
        assert patch_res.json()["is_active"] is False

        patch_res2 = await client.patch(f"/api/lessons/{lesson_id_export}", json={"is_active": True}, headers=headers_a)
        assert patch_res2.status_code == 200
        assert patch_res2.json()["is_active"] is True

        # =================================================================
        # PHASE 9: Ask This Question Again & Future Demonstration
        # =================================================================

        # Step 1: Re-evaluate with Ask This Question Again
        ask_again_payload = {
            "message_id": message_id_2,
            "conversation_id": conversation_id,
        }
        ask_again_res = await client.post("/api/ask-again", json=ask_again_payload, headers=headers_a)
        assert ask_again_res.status_code == 200
        aa_data = ask_again_res.json()

        assert aa_data["lesson_retrieved"] is True
        assert aa_data["new_answer"] == export_correct_answer
        assert str(aa_data["lesson_used"]) == str(lesson_id_export)

        # Step 2: Future Customer Demonstration (paraphrased question)
        # A new customer asks a similar future question to Nexora
        future_customer_q = "How frequently are database backups performed?"
        future_res = await client.post("/api/chat", json={
            "business_token": biz_a_token,
            "question": future_customer_q,
        })
        assert future_res.status_code == 200
        future_data = future_res.json()

        # Verified lesson must be retrieved and returned!
        assert not future_data["is_pending"]
        assert future_data["lesson_used"] is not None
        assert str(future_data["lesson_used"]) == str(lesson_id_export)
        assert "60 minutes" in future_data["answer"]

        # Step 3: Cross-Tenant Verification on Future Question
        # Customer asks Business B (Solaria Solar) the same backup question
        solaria_future_res = await client.post("/api/chat", json={
            "business_token": biz_b_token,
            "question": future_customer_q,
        })
        assert solaria_future_res.status_code == 200
        solaria_data = solaria_future_res.json()

        # Solaria Solar must NOT retrieve Nexora's lesson!
        assert solaria_data["is_pending"] is True
        assert solaria_data["answer"] == "Thank you! The team will reply to you soon."
        assert solaria_data["lesson_used"] is None
