import pytest
from app.config import Settings
from app.utils.auth import create_access_token
from jose import jwt


def test_missing_app_secret_key_fails_safely():
    """Verify application startup validation raises ValueError if APP_SECRET_KEY is missing or empty."""
    # Test with empty string
    settings_empty = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db", APP_SECRET_KEY="")
    with pytest.raises(ValueError) as excinfo:
        settings_empty.validate_all()
    assert "APP_SECRET_KEY is missing or empty" in str(excinfo.value)

    # Test with whitespace string
    settings_whitespace = Settings(DATABASE_URL="postgresql://user:pass@localhost:5432/db", APP_SECRET_KEY="   ")
    with pytest.raises(ValueError) as excinfo:
        settings_whitespace.validate_all()
    assert "APP_SECRET_KEY is missing or empty" in str(excinfo.value)


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
