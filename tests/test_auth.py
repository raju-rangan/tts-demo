"""Unit tests for Target GCP Project Authentication Verifier."""
from unittest.mock import patch, MagicMock
from scripts.verify_gcp_auth import get_adc_info, check_live_project_access

def test_adc_info_missing(tmp_path):
    """Verify missing ADC credentials file returns False."""
    fake_path = str(tmp_path / "non_existent_adc.json")
    with patch("os.path.expanduser", return_value=fake_path):
        exists, quota_proj, path = get_adc_info()
        assert exists is False
        assert quota_proj is None

def test_adc_info_with_quota_project(tmp_path):
    """Verify ADC quota_project_id is extracted correctly."""
    adc_file = tmp_path / "adc.json"
    adc_file.write_text('{"client_id": "xyz", "quota_project_id": "cs-poc-target-123"}')

    with patch("os.path.expanduser", return_value=str(adc_file)):
        exists, quota_proj, path = get_adc_info()
        assert exists is True
        assert quota_proj == "cs-poc-target-123"

def test_live_project_access_success():
    """Verify live project access check when storage client succeeds."""
    mock_creds = MagicMock()
    mock_client = MagicMock()
    mock_client.list_buckets.return_value = []

    with patch("google.auth.default", return_value=(mock_creds, "cs-poc-target-123")), \
         patch("google.cloud.storage.Client", return_value=mock_client):
        success, msg = check_live_project_access("cs-poc-target-123")
        assert success is True
        assert "Successfully" in msg

def test_live_project_access_permission_denied():
    """Verify live project access check when permission is denied on project."""
    mock_creds = MagicMock()
    mock_client = MagicMock()
    mock_client.list_buckets.side_effect = Exception("403 Forbidden: Caller does not have required permission")

    with patch("google.auth.default", return_value=(mock_creds, "cs-poc-target-123")), \
         patch("google.cloud.storage.Client", return_value=mock_client):
        success, msg = check_live_project_access("cs-poc-target-123")
        assert success is False
        assert "Permission denied" in msg


# ------------------------------------------------------------------------------
# Tests for Web UI Google Cloud Identity Platform (GCIP) Authentication
# ------------------------------------------------------------------------------
from fastapi.testclient import TestClient
from fastapi import HTTPException
from src.ui.app import app, get_current_user, verify_gcip_token

def test_api_auth_config():
    """Verify /api/auth/config endpoint returns public configuration."""
    client = TestClient(app)
    resp = client.get("/api/auth/config")
    assert resp.status_code == 200
    data = resp.json()
    assert "project_id" in data
    assert "api_key" in data
    assert "auth_domain" in data
    assert "enable_demo_auth" in data
    assert "has_gcip" in data

def test_verify_gcip_token_valid():
    """Verify valid GCIP Firebase token returns claims dictionary."""
    mock_claims = {
        "email": "user@altostrat.com",
        "name": "Altostrat User",
        "sub": "user_12345",
        "picture": "https://lh3.googleusercontent.com/photo.jpg"
    }
    with patch("src.ui.app.google_id_token.verify_firebase_token", return_value=mock_claims), \
         patch.dict("os.environ", {"GCP_PROJECT_ID": "test-project"}):
        claims = verify_gcip_token("fake-valid-jwt-token")
        assert claims == mock_claims
        assert claims["email"] == "user@altostrat.com"

def test_verify_gcip_token_invalid():
    """Verify invalid GCIP token returns None."""
    with patch("src.ui.app.google_id_token.verify_firebase_token", side_effect=ValueError("Token expired")), \
         patch.dict("os.environ", {"GCP_PROJECT_ID": "test-project"}):
        claims = verify_gcip_token("expired-jwt-token")
        assert claims is None

def test_get_current_user_with_valid_gcip_token():
    """Verify get_current_user authenticates valid GCIP token and attaches default creator persona."""
    mock_claims = {
        "email": "admin@altostrat.com",
        "name": "Admin Specialist",
        "sub": "uid_999",
        "picture": "https://example.com/avatar.png"
    }
    with patch("src.ui.app.verify_gcip_token", return_value=mock_claims), \
         patch("src.ui.app.ALLOWED_DOMAINS", ["altostrat.com"]), \
         patch("src.ui.app.ALLOWED_USERS", []):
        user = get_current_user(authorization="Bearer valid-token-123")
        assert user["email"] == "admin@altostrat.com"
        assert user["google_name"] == "Admin Specialist"
        assert user["name"] == "Sarah Jenkins"
        assert user["role"] == "Chief Communications Officer"
        assert user["avatar"] == "/static/avatars/creator_sarah.jpg"
        assert user["persona_type"] == "creator"

def test_get_current_user_with_auditor_persona():
    """Verify get_current_user switches to auditor persona when requested."""
    mock_claims = {
        "email": "admin@altostrat.com",
        "name": "Admin Specialist",
        "sub": "uid_999",
        "picture": "https://example.com/avatar.png"
    }
    with patch("src.ui.app.verify_gcip_token", return_value=mock_claims), \
         patch("src.ui.app.ALLOWED_DOMAINS", ["altostrat.com"]), \
         patch("src.ui.app.ALLOWED_USERS", []):
        user = get_current_user(authorization="Bearer valid-token-123", x_apex_persona="auditor")
        assert user["email"] == "admin@altostrat.com"
        assert user["name"] == "David Chen"
        assert user["role"] == "VP Regulatory Compliance"
        assert user["avatar"] == "/static/avatars/auditor_david.jpg"
        assert user["persona_type"] == "auditor"

def test_get_current_user_domain_restriction_blocked():
    """Verify get_current_user rejects email from unauthorized domain."""
    mock_claims = {
        "email": "intruder@external-unauthorized.com",
        "name": "Intruder",
        "sub": "uid_bad"
    }
    with patch("src.ui.app.verify_gcip_token", return_value=mock_claims), \
         patch("src.ui.app.ALLOWED_DOMAINS", ["altostrat.com", "google.com"]), \
         patch("src.ui.app.ALLOWED_USERS", []):
        try:
            get_current_user(authorization="Bearer token-bad-domain")
            assert False, "Should have raised HTTPException 403"
        except HTTPException as e:
            assert e.status_code == 403
            assert "domain '@external-unauthorized.com' is not authorized" in e.detail

def test_get_current_user_demo_auth_success():
    """Verify get_current_user supports demo session when ENABLE_DEMO_AUTH is true."""
    fake_token = "demo_session_test_token"
    fake_session = {
        "user": {
            "email": "admin@apexbank.com",
            "name": "Sarah Jenkins",
            "role": "Chief Communications Officer",
            "department": "Digital Wealth"
        },
        "created_at": 123456789.0
    }
    with patch.dict("src.ui.app.ACTIVE_SESSIONS", {fake_token: fake_session}), \
         patch("src.ui.app.ENABLE_DEMO_AUTH", True):
        user = get_current_user(authorization=f"Bearer {fake_token}", x_apex_persona="creator")
        assert user["email"] == "admin@apexbank.com"
        assert user["name"] == "Sarah Jenkins"
        assert user["persona_type"] == "creator"
