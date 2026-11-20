"""
Phase 2 Authentication and Multi-Tenant Isolation Tests
Tests:
1. Business owner registration and login.
2. Secure JWT issuance and verification.
3. Protected dashboard endpoint access control.
4. Business isolation between two independent tenants.
5. Customer anonymous public chat access via public widget token.
6. Rejection of invalid or forged business tokens.
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_owner_registration_and_widget_token():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        biz_name = f"Acme Store {uuid.uuid4().hex[:4]}"
        email = f"owner_{uuid.uuid4().hex[:6]}@acme.com"
        reg_payload = {
            "business_name": biz_name,
            "full_name": "Alice Acme",
            "email": email,
            "password": "StrongPassword123!",
            "business_description": "Online retailer"
        }
        res = await client.post("/api/auth/register", json=reg_payload)
        assert res.status_code == 201, res.text
        data = res.json()

        assert "access_token" in data
        assert "business_id" in data
        assert "widget_token" in data
        assert data["widget_token"].startswith("sb_pub_")
        assert data["full_name"] == "Alice Acme"

        # Check /api/auth/me with the token
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_res = await client.get("/api/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["email"] == email
        assert me_data["is_owner"] is True
        assert me_data["business_name"] == biz_name
        assert me_data["widget_token"] == data["widget_token"]


@pytest.mark.asyncio
async def test_unauthorized_dashboard_access_rejected():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # No token
        res1 = await client.get("/api/auth/me")
        assert res1.status_code == 401

        # Invalid token
        res2 = await client.get("/api/auth/me", headers={"Authorization": "Bearer invalid_token_12345"})
        assert res2.status_code == 401

        # Protected conversation endpoint without token
        res3 = await client.get("/api/conversations")
        assert res3.status_code == 401


@pytest.mark.asyncio
async def test_two_tenants_multi_tenant_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register Tenant A
        res_a = await client.post("/api/auth/register", json={
            "business_name": f"Tenant Alpha {uuid.uuid4().hex[:4]}",
            "full_name": "Alpha Owner",
            "email": f"alpha_{uuid.uuid4().hex[:6]}@alpha.com",
            "password": "Password123!",
        })
        assert res_a.status_code == 201
        data_a = res_a.json()
        token_a = data_a["access_token"]
        biz_a_id = data_a["business_id"]

        # Register Tenant B
        res_b = await client.post("/api/auth/register", json={
            "business_name": f"Tenant Beta {uuid.uuid4().hex[:4]}",
            "full_name": "Beta Owner",
            "email": f"beta_{uuid.uuid4().hex[:6]}@beta.com",
            "password": "Password123!",
        })
        assert res_b.status_code == 201
        data_b = res_b.json()
        token_b = data_b["access_token"]
        biz_b_id = data_b["business_id"]

        # Ensure different business IDs and different widget tokens
        assert biz_a_id != biz_b_id
        assert data_a["widget_token"] != data_b["widget_token"]

        # Tenant B cannot see Tenant A's conversations
        convs_b = await client.get("/api/conversations", headers={"Authorization": f"Bearer {token_b}"})
        assert convs_b.status_code == 200
        for conv in convs_b.json():
            assert conv["business_id"] == biz_b_id
            assert conv["business_id"] != biz_a_id


@pytest.mark.asyncio
async def test_customer_public_access_rules():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register a business first
        res = await client.post("/api/auth/register", json={
            "business_name": f"Customer Portal {uuid.uuid4().hex[:4]}",
            "full_name": "Support Lead",
            "email": f"lead_{uuid.uuid4().hex[:6]}@portal.com",
            "password": "Password123!",
        })
        assert res.status_code == 201
        biz_data = res.json()
        widget_token = biz_data["widget_token"]
        slug = biz_data["business_slug"]

        # 1. Customer accesses public info by widget token WITHOUT authentication
        info_res = await client.get(f"/api/chat/public/info?token={widget_token}")
        assert info_res.status_code == 200
        info = info_res.json()
        assert info["slug"] == slug
        assert info["widget_token"] == widget_token
        # Ensure private owner details are NOT in public response
        assert "owner" not in info
        assert "hashed_password" not in info

        # 2. Customer accesses public info by slug
        info_slug_res = await client.get(f"/api/widget/{slug}")
        assert info_slug_res.status_code == 200
        assert info_slug_res.json()["business_slug"] == slug

        # 3. Customer submits question using public widget token anonymously (no auth)
        chat_res = await client.post("/api/chat", json={
            "business_token": widget_token,
            "question": "What are your support hours?",
        })
        assert chat_res.status_code == 200
        chat_data = chat_res.json()
        assert "answer" in chat_data
        assert "conversation_id" in chat_data

        # 4. Customer submits question with optional email & name for follow up
        followup_res = await client.post("/api/chat", json={
            "business_token": widget_token,
            "question": "Can someone call me back about my invoice?",
            "customer_name": "John Customer",
            "customer_email": "john.customer@example.com",
        })
        assert followup_res.status_code == 200

        # 5. Customer with fake or invalid token is rejected
        bad_token_res = await client.post("/api/chat", json={
            "business_token": "sb_pub_forged_token_000000",
            "question": "Is this allowed?",
        })
        assert bad_token_res.status_code == 404
