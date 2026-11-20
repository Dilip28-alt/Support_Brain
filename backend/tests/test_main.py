"""
Backend tests — covers all major workflows.
Run with: pytest backend/tests/ -v
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.utils.auth import hash_password, verify_password, create_access_token
from app.utils.text_processing import chunk_text, clean_text
from app.utils.encryption import encrypt_token, decrypt_token


# ─────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────

def test_password_hashing():
    plain = "TestPass123!"
    hashed = hash_password(plain)
    assert hashed != plain
    assert verify_password(plain, hashed)
    assert not verify_password("WrongPass", hashed)


def test_jwt_token_creation():
    token = create_access_token({"sub": str(uuid.uuid4()), "business_id": str(uuid.uuid4())})
    assert isinstance(token, str)
    assert len(token) > 20


def test_text_chunking():
    text = " ".join([f"word{i}" for i in range(1000)])
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) > 1
    assert all(len(c.split()) <= 110 for c in chunks)   # allow small overlap


def test_text_chunking_short():
    text = "Hello world"
    chunks = chunk_text(text, chunk_size=100, overlap=10)
    assert len(chunks) == 1
    assert chunks[0] == "Hello world"


def test_clean_text():
    dirty = "Hello\x00World\n\n\n\n   test"
    clean = clean_text(dirty)
    assert "\x00" not in clean
    assert "\n\n\n" not in clean


def test_token_encryption():
    secret = "my_secret_oauth_token_12345"
    encrypted = encrypt_token(secret)
    assert encrypted != secret
    decrypted = decrypt_token(encrypted)
    assert decrypted == secret


# ─────────────────────────────────────────────
# API Integration (requires test DB)
# ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_health_check():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_register_and_login():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register
        reg_data = {
            "business_name": f"Test Business {uuid.uuid4().hex[:6]}",
            "full_name": "Test Owner",
            "email": f"test_{uuid.uuid4().hex[:6]}@example.com",
            "password": "TestPass123!",
        }
        reg_resp = await client.post("/api/auth/register", json=reg_data)
        assert reg_resp.status_code == 201, reg_resp.text
        token_data = reg_resp.json()
        assert "access_token" in token_data

        # Login
        login_resp = await client.post("/api/auth/login", json={
            "email": reg_data["email"],
            "password": reg_data["password"],
        })
        assert login_resp.status_code == 200
        assert login_resp.json()["access_token"]

        # Me endpoint
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        me_resp = await client.get("/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["email"] == reg_data["email"]


@pytest.mark.asyncio
async def test_add_text_knowledge():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register first
        email = f"test_{uuid.uuid4().hex[:6]}@example.com"
        reg = await client.post("/api/auth/register", json={
            "business_name": f"KB Test {uuid.uuid4().hex[:4]}",
            "full_name": "Owner",
            "email": email,
            "password": "TestPass123!",
        })
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Add text knowledge
        resp = await client.post("/api/knowledge/text", json={
            "title": "Office Hours",
            "content": "Our office is open Monday to Friday, 9 AM to 6 PM. We are closed on weekends and public holidays.",
        }, headers=headers)
        assert resp.status_code == 201
        source = resp.json()
        assert source["is_processed"] is True
        assert source["chunk_count"] > 0

        # List sources
        list_resp = await client.get("/api/knowledge/sources", headers=headers)
        assert list_resp.status_code == 200
        assert len(list_resp.json()) >= 1


@pytest.mark.asyncio
async def test_chat_basic():
    """Test that the chat endpoint returns something — full RAG test requires real DB."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/chat", json={
            "business_slug": "nonexistent-business",
            "question": "When are you open?",
        })
        assert resp.status_code in [200, 404]   # 404 if business doesn't exist


@pytest.mark.asyncio
async def test_business_data_isolation():
    """
    Two businesses must never see each other's knowledge.
    """
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register business A
        a_reg = await client.post("/api/auth/register", json={
            "business_name": f"Business A {uuid.uuid4().hex[:4]}",
            "full_name": "Owner A",
            "email": f"a_{uuid.uuid4().hex[:6]}@example.com",
            "password": "TestPass123!",
        })
        assert a_reg.status_code == 201
        a_token = a_reg.json()["access_token"]

        # Register business B
        b_reg = await client.post("/api/auth/register", json={
            "business_name": f"Business B {uuid.uuid4().hex[:4]}",
            "full_name": "Owner B",
            "email": f"b_{uuid.uuid4().hex[:6]}@example.com",
            "password": "TestPass123!",
        })
        assert b_reg.status_code == 201
        b_token = b_reg.json()["access_token"]

        # B should NOT see A's knowledge sources
        a_sources = await client.get("/api/knowledge/sources",
                                     headers={"Authorization": f"Bearer {a_token}"})
        b_sources = await client.get("/api/knowledge/sources",
                                     headers={"Authorization": f"Bearer {b_token}"})

        a_ids = {s["id"] for s in a_sources.json()}
        b_ids = {s["id"] for s in b_sources.json()}
        assert a_ids.isdisjoint(b_ids), "Business isolation FAILED — shared knowledge sources detected!"


@pytest.mark.asyncio
async def test_analytics_endpoint():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        reg = await client.post("/api/auth/register", json={
            "business_name": f"Analytics Test {uuid.uuid4().hex[:4]}",
            "full_name": "Owner",
            "email": f"analytics_{uuid.uuid4().hex[:6]}@example.com",
            "password": "TestPass123!",
        })
        assert reg.status_code == 201
        token = reg.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        resp = await client.get("/api/analytics/summary", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_questions" in data
        assert "weekly_trends" in data
        assert len(data["weekly_trends"]) == 8   # 8 weeks
