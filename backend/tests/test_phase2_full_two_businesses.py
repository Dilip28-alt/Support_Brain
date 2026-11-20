"""
End-to-End Verification of Phase 2:
- Business Registration
- Login & JWT Authentication
- Bcrypt Password Hashing
- Protected Routes Validation
- Strict Multi-Tenant Data Isolation between Two Separate Businesses (Alpha & Beta)
"""
import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.utils.auth import verify_password


@pytest.mark.asyncio
async def test_full_two_businesses_isolation():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # ============================================================
        # 1. Register Two Separate Businesses: Alpha & Beta
        # ============================================================
        alpha_biz_name = f"Alpha Innovations {uuid.uuid4().hex[:4]}"
        alpha_email = f"alpha_owner_{uuid.uuid4().hex[:6]}@alpha.com"
        alpha_password = "AlphaPassword2026!"

        res_alpha_reg = await client.post("/api/auth/register", json={
            "business_name": alpha_biz_name,
            "full_name": "Alpha CEO",
            "email": alpha_email,
            "password": alpha_password,
            "business_description": "AI & Robotics Solutions"
        })
        assert res_alpha_reg.status_code == 201, res_alpha_reg.text
        alpha_auth = res_alpha_reg.json()
        alpha_token = alpha_auth["access_token"]
        alpha_biz_id = alpha_auth["business_id"]
        alpha_slug = alpha_auth["business_slug"]
        alpha_widget_token = alpha_auth["widget_token"]

        beta_biz_name = f"Beta Logistics {uuid.uuid4().hex[:4]}"
        beta_email = f"beta_owner_{uuid.uuid4().hex[:6]}@beta.com"
        beta_password = "BetaPassword2026!"

        res_beta_reg = await client.post("/api/auth/register", json={
            "business_name": beta_biz_name,
            "full_name": "Beta Manager",
            "email": beta_email,
            "password": beta_password,
            "business_description": "Global Freight Forwarding"
        })
        assert res_beta_reg.status_code == 201, res_beta_reg.text
        beta_auth = res_beta_reg.json()
        beta_token = beta_auth["access_token"]
        beta_biz_id = beta_auth["business_id"]
        beta_slug = beta_auth["business_slug"]
        beta_widget_token = beta_auth["widget_token"]

        # Assert fundamental business identity separation
        assert alpha_biz_id != beta_biz_id
        assert alpha_slug != beta_slug
        assert alpha_widget_token != beta_widget_token
        assert alpha_widget_token.startswith("sb_pub_")
        assert beta_widget_token.startswith("sb_pub_")

        # ============================================================
        # 2. Login & Password Verification
        # ============================================================
        # Good login Alpha
        login_res_alpha = await client.post("/api/auth/login", json={
            "email": alpha_email,
            "password": alpha_password
        })
        assert login_res_alpha.status_code == 200
        assert login_res_alpha.json()["business_id"] == alpha_biz_id

        # Bad password Alpha
        bad_pw_res = await client.post("/api/auth/login", json={
            "email": alpha_email,
            "password": "WrongPassword999!"
        })
        assert bad_pw_res.status_code == 401

        # Nonexistent user
        no_user_res = await client.post("/api/auth/login", json={
            "email": "ghost_user_123@nowhere.com",
            "password": "SomePassword123!"
        })
        assert no_user_res.status_code == 401

        # ============================================================
        # 3. Protected Routes Reject Unauthenticated Requests
        # ============================================================
        protected_endpoints = [
            ("GET", "/api/auth/me"),
            ("GET", "/api/knowledge/sources"),
            ("POST", "/api/knowledge/text"),
            ("GET", "/api/conversations"),
            ("GET", "/api/pending/"),
            ("GET", "/api/lessons/"),
            ("POST", "/api/lessons/"),
            ("GET", "/api/analytics/summary"),
            ("GET", "/api/email/inbox"),
        ]
        for method, endpoint in protected_endpoints:
            if method == "GET":
                r = await client.get(endpoint)
            else:
                r = await client.post(endpoint, json={})
            assert r.status_code in [401, 403], f"Endpoint {endpoint} allowed unauthenticated access! Status: {r.status_code}"

        # ============================================================
        # 4. Strict Multi-Tenant Knowledge Isolation
        # ============================================================
        alpha_headers = {"Authorization": f"Bearer {alpha_token}"}
        beta_headers = {"Authorization": f"Bearer {beta_token}"}

        # Alpha uploads knowledge
        alpha_kb_res = await client.post("/api/knowledge/text", json={
            "title": "Alpha Confidential Robotics Warranty",
            "content": "All Alpha units carry a 5-year replacement guarantee."
        }, headers=alpha_headers)
        assert alpha_kb_res.status_code == 201
        alpha_source_id = alpha_kb_res.json()["id"]

        # Beta uploads knowledge
        beta_kb_res = await client.post("/api/knowledge/text", json={
            "title": "Beta Air Cargo Fuel Surcharges",
            "content": "Beta Air Cargo applies an 8% seasonal fuel charge."
        }, headers=beta_headers)
        assert beta_kb_res.status_code == 201
        beta_source_id = beta_kb_res.json()["id"]

        # Alpha lists knowledge -> MUST NOT SEE Beta's knowledge
        alpha_sources_res = await client.get("/api/knowledge/sources", headers=alpha_headers)
        assert alpha_sources_res.status_code == 200
        alpha_sources = alpha_sources_res.json()
        alpha_source_titles = [s["title"] for s in alpha_sources]
        assert "Alpha Confidential Robotics Warranty" in alpha_source_titles
        assert "Beta Air Cargo Fuel Surcharges" not in alpha_source_titles

        # Beta lists knowledge -> MUST NOT SEE Alpha's knowledge
        beta_sources_res = await client.get("/api/knowledge/sources", headers=beta_headers)
        assert beta_sources_res.status_code == 200
        beta_sources = beta_sources_res.json()
        beta_source_titles = [s["title"] for s in beta_sources]
        assert "Beta Air Cargo Fuel Surcharges" in beta_source_titles
        assert "Alpha Confidential Robotics Warranty" not in beta_source_titles

        # Cross-tenant ID probing: Alpha attempts to inspect Beta's source chunks
        probe_res = await client.get(f"/api/knowledge/sources/{beta_source_id}/chunks", headers=alpha_headers)
        assert probe_res.status_code == 404, "Alpha was able to probe Beta's source chunks!"

        # Cross-tenant ID deletion: Alpha attempts to delete Beta's source
        delete_probe_res = await client.delete(f"/api/knowledge/sources/{beta_source_id}", headers=alpha_headers)
        assert delete_probe_res.status_code == 404, "Alpha was able to delete Beta's knowledge source!"

        # ============================================================
        # 5. Strict Multi-Tenant Lessons Isolation
        # ============================================================
        # Alpha creates a lesson
        alpha_lesson_res = await client.post("/api/lessons/", json={
            "question": "Can I get a refund on robotics?",
            "original_answer": "No refunds.",
            "corrected_answer": "Alpha grants refunds within 30 days.",
            "owner_comment": "Owner policy update"
        }, headers=alpha_headers)
        assert alpha_lesson_res.status_code == 201
        alpha_lesson_id = alpha_lesson_res.json()["id"]

        # Beta queries lessons -> MUST BE EMPTY for Beta
        beta_lessons_res = await client.get("/api/lessons/", headers=beta_headers)
        assert beta_lessons_res.status_code == 200
        beta_lessons = beta_lessons_res.json()
        assert not any(l["id"] == alpha_lesson_id for l in beta_lessons)

        # Cross-tenant ID mutation: Beta attempts to patch Alpha's lesson
        patch_probe_res = await client.patch(f"/api/lessons/{alpha_lesson_id}", json={
            "corrected_answer": "Hacked by Beta"
        }, headers=beta_headers)
        assert patch_probe_res.status_code == 404, "Beta was able to patch Alpha's lesson!"

        # ============================================================
        # 6. Customer Chat Isolation via Public Widget Tokens
        # ============================================================
        # Customer chats with Alpha using Alpha's public widget token
        chat_alpha_res = await client.post("/api/chat", json={
            "business_token": alpha_widget_token,
            "question": "What is your robotics warranty period?",
            "customer_name": "Alice Customer",
            "customer_email": "alice@customer.com"
        })
        assert chat_alpha_res.status_code == 200
        alpha_chat_data = chat_alpha_res.json()
        alpha_conv_id = alpha_chat_data["conversation_id"]

        # Alpha dashboard lists conversations -> Sees the customer chat
        alpha_convs_res = await client.get("/api/conversations", headers=alpha_headers)
        assert alpha_convs_res.status_code == 200
        alpha_conv_ids = [c["id"] for c in alpha_convs_res.json()]
        assert str(alpha_conv_id) in [str(cid) for cid in alpha_conv_ids]

        # Beta dashboard lists conversations -> MUST NOT SEE Alpha's customer chat
        beta_convs_res = await client.get("/api/conversations", headers=beta_headers)
        assert beta_convs_res.status_code == 200
        beta_conv_ids = [c["id"] for c in beta_convs_res.json()]
        assert str(alpha_conv_id) not in [str(cid) for cid in beta_conv_ids]

        # Beta attempts to read messages of Alpha's conversation
        beta_read_conv_res = await client.get(f"/api/conversations/{alpha_conv_id}/messages", headers=beta_headers)
        assert beta_read_conv_res.status_code == 404, "Beta was able to read Alpha's customer chat messages!"
