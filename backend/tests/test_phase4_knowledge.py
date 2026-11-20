"""
Phase 4 Automated Tests:
- Text Ingestion & Chunking
- PDF Text Extraction & Vector Embeddings
- Website URL Ingestion & SSRF Protection
- View, Edit, and Delete Operations for Knowledge Sources and Chunks
"""
import pytest
import uuid
import io
import fitz  # PyMuPDF
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.fixture
async def auth_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Register a unique business for testing
        biz_name = f"Knowledge Tenant {uuid.uuid4().hex[:4]}"
        email = f"kb_owner_{uuid.uuid4().hex[:6]}@knowledge.com"
        res = await client.post("/api/auth/register", json={
            "business_name": biz_name,
            "full_name": "KB Owner",
            "email": email,
            "password": "Password123!",
        })
        assert res.status_code == 201
        token = res.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        yield client, headers


@pytest.mark.asyncio
async def test_text_ingestion_and_chunking(auth_client):
    client, headers = auth_client

    title = "Customer Support & Return Policy"
    content = """Support Brain provides automated AI customer service.
Customers can request refunds within 30 days of purchase with proof of order.
Standard shipping takes 3 to 5 business days across North America.
Express shipping delivers within 24 hours for all orders placed before 2 PM.
For technical assistance, customer support is available Monday through Friday from 9 AM to 6 PM EST."""

    # 1. Ingest text
    res = await client.post("/api/knowledge/text", json={
        "title": title,
        "content": content
    }, headers=headers)
    assert res.status_code == 201, res.text
    source = res.json()
    source_id = source["id"]
    assert source["title"] == title
    assert source["source_type"] == "text"
    assert source["is_processed"] is True
    assert source["chunk_count"] >= 1

    # 2. View individual chunks
    chunks_res = await client.get(f"/api/knowledge/sources/{source_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert len(chunks) == source["chunk_count"]
    assert chunks[0]["source_id"] == source_id
    assert "refunds within 30 days" in chunks[0]["content"]


@pytest.mark.asyncio
async def test_pdf_extraction_and_embedding(auth_client):
    client, headers = auth_client

    # Create a small valid PDF in-memory using PyMuPDF (fitz)
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text(fitz.Point(50, 72), "Support Brain Hardware Warranty Document.\nAll equipment includes a 2-year full replacement warranty covering parts and labor.")
    pdf_bytes = doc.tobytes()
    doc.close()

    # Upload PDF
    files = {"file": ("warranty_policy.pdf", pdf_bytes, "application/pdf")}
    res = await client.post("/api/knowledge/pdf", files=files, headers=headers)
    assert res.status_code == 201, res.text
    source = res.json()
    source_id = source["id"]

    assert source["source_type"] == "pdf"
    assert source["file_name"] == "warranty_policy.pdf"
    assert source["is_processed"] is True
    assert source["chunk_count"] >= 1

    # Verify chunks extracted from PDF
    chunks_res = await client.get(f"/api/knowledge/sources/{source_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert any("2-year full replacement warranty" in c["content"] for c in chunks)


@pytest.mark.asyncio
async def test_url_ssrf_protection(auth_client):
    client, headers = auth_client

    # 1. SSRF attack test: internal localhost URL must be blocked
    res_local = await client.post("/api/knowledge/url", json={
        "url": "http://127.0.0.1:8000/api/health",
        "title": "Localhost Attack"
    }, headers=headers)
    assert res_local.status_code in [400, 422], f"Localhost was not blocked! Status: {res_local.status_code}"

    # 2. SSRF attack test: cloud metadata IP must be blocked
    res_meta = await client.post("/api/knowledge/url", json={
        "url": "http://169.254.169.254/latest/meta-data/",
        "title": "Cloud Metadata Attack"
    }, headers=headers)
    assert res_meta.status_code in [400, 422], f"Metadata IP was not blocked! Status: {res_meta.status_code}"

    # 3. Invalid scheme test
    res_scheme = await client.post("/api/knowledge/url", json={
        "url": "file:///etc/passwd",
        "title": "File Scheme Attack"
    }, headers=headers)
    assert res_scheme.status_code in [400, 422]


@pytest.mark.asyncio
async def test_view_edit_and_delete_operations(auth_client):
    client, headers = auth_client

    # Ingest initial text
    res = await client.post("/api/knowledge/text", json={
        "title": "Original Product Guide",
        "content": "Original content: Product version 1.0 is officially deprecated."
    }, headers=headers)
    assert res.status_code == 201
    source_id = res.json()["id"]

    # 1. View all sources
    list_res = await client.get("/api/knowledge/sources", headers=headers)
    assert list_res.status_code == 200
    sources = list_res.json()
    assert any(s["id"] == source_id for s in sources)

    # 2. Edit source title and content
    edit_res = await client.patch(f"/api/knowledge/sources/{source_id}", json={
        "title": "Updated Product Guide 2026",
        "content": "Updated content: Product version 2.0 is now live and fully supported."
    }, headers=headers)
    assert edit_res.status_code == 200
    updated_source = edit_res.json()
    assert updated_source["title"] == "Updated Product Guide 2026"

    # Verify chunks were re-embedded with new content
    chunks_res = await client.get(f"/api/knowledge/sources/{source_id}/chunks", headers=headers)
    assert chunks_res.status_code == 200
    chunks = chunks_res.json()
    assert any("version 2.0 is now live" in c["content"] for c in chunks)
    assert not any("deprecated" in c["content"] for c in chunks)

    # 3. Delete knowledge source
    del_res = await client.delete(f"/api/knowledge/sources/{source_id}", headers=headers)
    assert del_res.status_code == 204

    # Verify source is gone
    get_res = await client.get(f"/api/knowledge/sources/{source_id}/chunks", headers=headers)
    assert get_res.status_code == 404
