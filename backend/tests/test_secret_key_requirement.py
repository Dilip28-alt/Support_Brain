import pytest
from unittest.mock import patch
from app.config import Settings
from app.main import lifespan
from fastapi import FastAPI
from jose import jwt


def test_missing_app_secret_key_fails_safely():
    """Verify application startup validation raises ValueError if APP_SECRET_KEY is missing or empty."""
    # Test with empty string
    settings_empty = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db", APP_SECRET_KEY="")
    with pytest.raises(ValueError) as excinfo:
        settings_empty.validate_all()
    error_msg = str(excinfo.value)
    assert "APP_SECRET_KEY" in error_msg
    assert "Application startup stopped" in error_msg
    assert "must be configured in environment variables" in error_msg

    # Test with whitespace string
    settings_whitespace = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db", APP_SECRET_KEY="   ")
    with pytest.raises(ValueError) as excinfo:
        settings_whitespace.validate_all()
    assert "APP_SECRET_KEY" in str(excinfo.value)


def test_valid_app_secret_key_succeeds_and_jwt_functions():
    """Verify application validation succeeds and JWT auth works when a valid secret is provided."""
    test_secret = "test-custom-app-secret-key-32-bytes-long!"
    settings_valid = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db", APP_SECRET_KEY=test_secret)
    # validate_all should not raise
    settings_valid.validate_all()

    # JWT generation and decoding works with configured secret
    payload = {"sub": "user-123", "business_id": "biz-456"}
    token = jwt.encode(payload, test_secret, algorithm="HS256")
    decoded = jwt.decode(token, test_secret, algorithms=["HS256"])
    assert decoded["sub"] == "user-123"
    assert decoded["business_id"] == "biz-456"


@pytest.mark.asyncio
async def test_app_startup_stops_without_app_secret_key():
    """Verify that the FastAPI application stops during startup lifespan if APP_SECRET_KEY is missing."""
    test_app = FastAPI()
    with patch("app.main.settings.APP_SECRET_KEY", ""):
        with pytest.raises(ValueError) as excinfo:
            async with lifespan(test_app):
                pass
        error_msg = str(excinfo.value)
        assert "APP_SECRET_KEY" in error_msg
        assert "Application startup stopped" in error_msg
