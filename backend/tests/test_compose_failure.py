import pytest
from unittest import mock
import uuid
from datetime import datetime, timezone

from app.models.models import (
    Business, User, EmailAccount, EmailMessage,
    EmailMessageStatus, EmailMessageDirection, EmailProcessingMode, EmailAccountStatus
)
from app.database import AsyncSessionLocal
from app.utils.auth import create_access_token, hash_password
from app.utils.encryption import encrypt_token
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_compose_email_gmail_failure_shows_error_and_saves_failed():
    """
    Test: In 'Compose', if Gmail fails to send:
    1. Returns HTTP 500 with descriptive error detail.
    2. Persists the email in database with status 'failed'.
    """
    uid = uuid.uuid4().hex[:6]
    biz_slug = f"test-compose-{uid}"

    # 1. Setup business, user, and connected Gmail account
    async with AsyncSessionLocal() as session:
        biz = Business(
            name="Compose Test Biz",
            slug=biz_slug,
            widget_token=f"sb_pub_{uid}",
            is_active=True,
        )
        session.add(biz)
        await session.flush()

        user = User(
            business_id=biz.id,
            email=f"owner_{uid}@testbiz.com",
            full_name="Compose Owner",
            hashed_password=hash_password("Pass123!"),
            is_active=True,
        )
        session.add(user)

        account = EmailAccount(
            business_id=biz.id,
            email_address=f"support@{biz_slug}.com",
            encrypted_access_token=encrypt_token("mock-gmail-token"),
            encrypted_refresh_token=encrypt_token("mock-refresh-token"),
            token_expiry=datetime.now(timezone.utc),
            processing_mode=EmailProcessingMode.review,
            status=EmailAccountStatus.connected,
        )
        session.add(account)
        await session.commit()
        biz_id = biz.id
        user_id = user.id

    token = create_access_token(data={"sub": str(user_id), "business_id": str(biz_id)})
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Mock Gmail API to simulate a send failure
    mock_service = mock.MagicMock()
    mock_service.users().messages().send().execute.side_effect = Exception("Gmail API 503 Service Unavailable")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with mock.patch("app.email.gmail_service._build_gmail_service", return_value=(mock_service, None)):
            res = await client.post("/api/email/compose", json={
                "recipient": "customer@example.com",
                "subject": "Important Account Update",
                "body": "Dear customer, your request has been reviewed.",
            }, headers=headers)

            # Assert 1: The app shows an error instead of pretending it succeeded
            assert res.status_code == 500
            assert "Gmail delivery failed" in res.json()["detail"]

    # 3. Assert 2: Database saves the email with status 'failed'
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select
        result = await session.execute(
            select(EmailMessage).where(
                EmailMessage.business_id == biz_id,
                EmailMessage.recipient == "customer@example.com",
                EmailMessage.direction == EmailMessageDirection.outgoing,
            )
        )
        saved_email = result.scalars().first()

        assert saved_email is not None, "Failed email record must be persisted in database"
        assert saved_email.status == EmailMessageStatus.failed, f"Expected status 'failed', got '{saved_email.status}'"
        assert saved_email.subject == "Important Account Update"
        assert saved_email.body_text == "Dear customer, your request has been reviewed."
        assert saved_email.sender == f"support@{biz_slug}.com"
