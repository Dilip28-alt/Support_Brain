"""
Support Brain — Phase 5 & 6 Integration Tests
Tests:
  1. Widget.js endpoint and public widget info resolution.
  2. Multi-tenant semantic retrieval with pgvector.
  3. Grounded Gemini answer generation with source citations (source title, chunk ID).
  4. Cross-tenant isolation (Business A never sees Business B knowledge).
  5. Lesson-first retrieval (verified owner lessons take strict precedence).
  6. Unknown-question fallback to "Thank you! The team will reply to you soon." and Pending Question creation.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select

from app.main import app
from app.database import AsyncSessionLocal
from app.models.models import (
    Business, User, KnowledgeSource, KnowledgeChunk,
    Lesson, PendingQuestion, PendingQuestionSource, KnowledgeSourceType
)
from app.ai.gemini_client import get_embedding
from app.utils.auth import hash_password


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
async def test_widget_js_served():
    """Verify /widget.js is served publicly with javascript media type."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/widget.js")
        assert resp.status_code == 200
        assert "javascript" in resp.headers.get("content-type", "")
        assert "Support Brain" in resp.text
        assert "data-business-token" in resp.text


@pytest.mark.asyncio
async def test_phase5_6_full_rag_pipeline():
    """Comprehensive test covering RAG retrieval, citations, business isolation, lessons, and fallback."""
    uid = uuid.uuid4().hex[:6]
    biz_a_slug = f"quantum-retail-{uid}"
    biz_b_slug = f"starlight-dental-{uid}"
    biz_a_token = f"sb_pub_quantum_{uid}"
    biz_b_token = f"sb_pub_starlight_{uid}"

    async with AsyncSessionLocal() as session:
        # 1. Create Business A
        biz_a = Business(
            name="Quantum Retail",
            slug=biz_a_slug,
            widget_token=biz_a_token,
            is_active=True,
        )
        session.add(biz_a)
        await session.flush()

        user_a = User(
            business_id=biz_a.id,
            email=f"owner_{uid}@quantum.com",
            full_name="Quantum Owner",
            hashed_password=hash_password("Secret123!"),
            is_active=True,
        )
        session.add(user_a)

        # 2. Ingest Business A knowledge
        ks_a = KnowledgeSource(
            business_id=biz_a.id,
            title="Quantum Return Policy",
            source_type=KnowledgeSourceType.text,
            is_processed=True,
            chunk_count=1,
        )
        session.add(ks_a)
        await session.flush()

        kc_a_text = (
            "All Quantum Retail purchases can be returned within 45 days of receipt. "
            "Refunds are issued to the original payment method within 3-5 business days. "
            "Free return shipping is included for all members."
        )
        emb_a = get_embedding(kc_a_text, task_type="RETRIEVAL_DOCUMENT")
        kc_a = KnowledgeChunk(
            business_id=biz_a.id,
            source_id=ks_a.id,
            chunk_index=0,
            content=kc_a_text,
            embedding=emb_a,
            token_count=40,
        )
        session.add(kc_a)

        # 3. Create Business B
        biz_b = Business(
            name="Starlight Dental",
            slug=biz_b_slug,
            widget_token=biz_b_token,
            is_active=True,
        )
        session.add(biz_b)
        await session.flush()

        user_b = User(
            business_id=biz_b.id,
            email=f"owner_{uid}@starlight.com",
            full_name="Starlight Owner",
            hashed_password=hash_password("Secret123!"),
            is_active=True,
        )
        session.add(user_b)

        # 4. Ingest Business B knowledge
        ks_b = KnowledgeSource(
            business_id=biz_b.id,
            title="Starlight Appointment Policy",
            source_type=KnowledgeSourceType.text,
            is_processed=True,
            chunk_count=1,
        )
        session.add(ks_b)
        await session.flush()

        kc_b_text = (
            "Appointments at Starlight Dental must be cancelled at least 24 hours in advance "
            "to avoid a fifty dollar late cancellation fee. Emergency walk-in visits are accepted "
            "on weekdays between 8am and 10am."
        )
        emb_b = get_embedding(kc_b_text, task_type="RETRIEVAL_DOCUMENT")
        kc_b = KnowledgeChunk(
            business_id=biz_b.id,
            source_id=ks_b.id,
            chunk_index=0,
            content=kc_b_text,
            embedding=emb_b,
            token_count=45,
        )
        session.add(kc_b)

        # 5. Create a Lesson for Business A
        lesson_a_q = "Do you ship internationally to Canada?"
        lesson_a_ans = "Yes! Quantum Retail ships to Canada via DHL Express in 3 business days for a flat rate of $15."
        lesson_a_emb = get_embedding(lesson_a_q, task_type="RETRIEVAL_DOCUMENT")
        lesson_a = Lesson(
            business_id=biz_a.id,
            question=lesson_a_q,
            original_answer="I don't know.",
            corrected_answer=lesson_a_ans,
            owner_comment="Verified international shipping policy.",
            embedding=lesson_a_emb,
            is_active=True,
        )
        session.add(lesson_a)

        await session.commit()
        biz_a_id = biz_a.id
        biz_b_id = biz_b.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ── Test Public Info Endpoint ──
        resp_info = await client.get(f"/api/chat/public/info?token={biz_a_token}")
        assert resp_info.status_code == 200
        assert resp_info.json()["name"] == "Quantum Retail"

        resp_info_b = await client.get(f"/api/chat/public/info?slug={biz_b_slug}")
        assert resp_info_b.status_code == 200
        assert resp_info_b.json()["name"] == "Starlight Dental"

        # ── Test 1: Grounded Semantic Retrieval with Citations ──
        # Ask Quantum Retail about refund window
        chat_req_1 = {
            "business_token": biz_a_token,
            "question": "What is your refund timeframe and how many days do I have to return?",
        }
        resp_1 = await client.post("/api/chat", json=chat_req_1)
        assert resp_1.status_code == 200, resp_1.text
        data_1 = resp_1.json()

        assert not data_1["is_pending"]
        assert data_1["confidence_score"] > 0.40
        assert len(data_1["source_chunks"]) > 0
        # Verify source citations contain title and chunk ID
        top_src = data_1["source_chunks"][0]
        assert top_src["source_title"] == "Quantum Return Policy"
        assert top_src["chunk_id"] is not None
        assert "45 days" in top_src["content"]
        assert "45" in data_1["answer"] or "return" in data_1["answer"].lower()

        # ── Test 2: Cross-Tenant Isolation ──
        # Ask Quantum Retail about dental late fees (knowledge belonging ONLY to Starlight Dental)
        chat_req_2 = {
            "business_token": biz_a_token,
            "question": "What is the fee if I cancel my dental appointment late?",
        }
        resp_2 = await client.post("/api/chat", json=chat_req_2)
        assert resp_2.status_code == 200
        data_2 = resp_2.json()

        # Must NOT return Starlight's dental fee!
        assert "fifty dollar" not in data_2["answer"].lower()
        assert "50" not in data_2["answer"]
        # Must trigger fallback and pending question
        assert data_2["is_pending"] is True
        assert data_2["answer"] == "Thank you! The team will reply to you soon."
        assert len(data_2["source_chunks"]) == 0

        # Verify pending question was logged in database for Business A
        async with AsyncSessionLocal() as session:
            pq_result = await session.execute(
                select(PendingQuestion).where(
                    PendingQuestion.business_id == biz_a_id,
                    PendingQuestion.customer_question == "What is the fee if I cancel my dental appointment late?",
                )
            )
            pq = pq_result.scalar_one_or_none()
            assert pq is not None
            assert pq.source == PendingQuestionSource.chat

        # ── Test 3: Lesson-First Retrieval ──
        # Ask Quantum Retail about Canada shipping (stored in lessons)
        chat_req_3 = {
            "business_token": biz_a_token,
            "question": "Do you ship internationally to Canada?",
        }
        resp_3 = await client.post("/api/chat", json=chat_req_3)
        assert resp_3.status_code == 200
        data_3 = resp_3.json()

        assert not data_3["is_pending"]
        assert data_3["lesson_used"] is not None
        assert "DHL Express" in data_3["answer"]
        assert "$15" in data_3["answer"]

        # ── Test 4: Unknown Question Fallback ──
        # Ask Starlight Dental completely ungrounded question
        chat_req_4 = {
            "business_slug": biz_b_slug,
            "question": "What is the warp speed limit of the starship Enterprise?",
            "customer_name": "James Kirk",
            "customer_email": "kirk@starfleet.org",
        }
        resp_4 = await client.post("/api/chat", json=chat_req_4)
        assert resp_4.status_code == 200
        data_4 = resp_4.json()

        assert data_4["is_pending"] is True
        assert data_4["answer"] == "Thank you! The team will reply to you soon."

        # Verify pending question in DB with customer info
        async with AsyncSessionLocal() as session:
            pq_b_res = await session.execute(
                select(PendingQuestion).where(
                    PendingQuestion.business_id == biz_b_id,
                    PendingQuestion.customer_question == "What is the warp speed limit of the starship Enterprise?",
                )
            )
            pq_b = pq_b_res.scalar_one_or_none()
            assert pq_b is not None
            assert pq_b.customer_name == "James Kirk"
            assert pq_b.customer_email == "kirk@starfleet.org"
            assert pq_b.source == PendingQuestionSource.chat
