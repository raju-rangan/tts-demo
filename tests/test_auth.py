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
from src.ui.app import app, get_current_user, verify_gcip_token, is_localhost_request

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
    assert "is_localhost" in data


def test_is_localhost_request():
    """Verify is_localhost_request accurately distinguishes local vs remote traffic."""
    from unittest.mock import MagicMock
    # 1. None request
    assert is_localhost_request(None) is False

    # 2. Host: localhost
    req_local = MagicMock()
    req_local.headers = {"host": "localhost:8000"}
    req_local.client.host = "127.0.0.1"
    req_local.url.hostname = "localhost"
    assert is_localhost_request(req_local) is True

    # 3. Host: 127.0.0.1:8000
    req_ip = MagicMock()
    req_ip.headers = {"host": "127.0.0.1:8000"}
    req_ip.client.host = "127.0.0.1"
    req_ip.url.hostname = "127.0.0.1"
    assert is_localhost_request(req_ip) is True

    # 4. Production Cloud Run host
    req_remote = MagicMock()
    req_remote.headers = {"host": "tts-studio-716595821548.us-central1.run.app"}
    req_remote.client.host = "35.192.0.1"
    req_remote.url.hostname = "tts-studio-716595821548.us-central1.run.app"
    assert is_localhost_request(req_remote) is False


def test_get_current_user_localhost_bypass():
    """Verify get_current_user automatically bypasses auth on localhost and binds active persona."""
    from unittest.mock import MagicMock
    req_local = MagicMock()
    req_local.headers = {"host": "localhost:8000"}
    req_local.client.host = "127.0.0.1"
    req_local.url.hostname = "localhost"

    # Default creator persona
    user_creator = get_current_user(request=req_local)
    assert user_creator["email"] == "local-dev@apexbank.com"
    assert user_creator["name"] == "Sarah Jenkins"
    assert user_creator["persona_type"] == "creator"
    assert user_creator["is_localhost"] is True

    # Switched auditor persona
    user_auditor = get_current_user(request=req_local, x_apex_persona="auditor")
    assert user_auditor["email"] == "local-dev@apexbank.com"
    assert user_auditor["name"] == "David Chen"
    assert user_auditor["persona_type"] == "auditor"
    assert user_auditor["is_localhost"] is True


def test_get_current_user_local_dev_token_bypass():
    """Verify get_current_user bypasses auth when local-dev-token is presented."""
    user = get_current_user(authorization="Bearer local-dev-token")
    assert user["email"] == "local-dev@apexbank.com"
    assert user["is_localhost"] is True

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
        assert user["role"] == "Senior Digital Communications Specialist"
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
        assert user["role"] == "Senior Regulatory Compliance Analyst"
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
            "role": "Senior Digital Communications Specialist",
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


def test_create_google_session_success():
    """Verify POST /api/auth/google-session authenticates allowed corporate user and enables persona selection."""
    client = TestClient(app)
    with patch("src.ui.app.ALLOWED_DOMAINS", ["altostrat.com", "google.com"]), \
         patch("src.ui.app.ALLOWED_USERS", []):
        resp = client.post("/api/auth/google-session", json={"email": "admin@rrangan.altostrat.com"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token"].startswith("google_")
        assert data["user"]["email"] == "admin@rrangan.altostrat.com"
        assert data["user"]["name"] == "Sarah Jenkins"

        token = data["token"]
        # Verify authenticated session can call /api/auth/me and switch persona to auditor
        me_resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}", "X-Apex-Persona": "auditor"}
        )
        assert me_resp.status_code == 200
        me_data = me_resp.json()
        assert me_data["user"]["name"] == "David Chen"
        assert me_data["user"]["role"] == "Senior Regulatory Compliance Analyst"
        assert me_data["user"]["persona_type"] == "auditor"


def test_create_google_session_forbidden_domain():
    """Verify POST /api/auth/google-session rejects unauthorized domains."""
    client = TestClient(app)
    with patch("src.ui.app.ALLOWED_DOMAINS", ["altostrat.com", "google.com"]), \
         patch("src.ui.app.ALLOWED_USERS", []):
        resp = client.post("/api/auth/google-session", json={"email": "user@unauthorized.com"})
        assert resp.status_code == 403
        assert "not authorized" in resp.json()["detail"]


def test_create_google_session_empty_email():
    """Verify POST /api/auth/google-session rejects empty email."""
    client = TestClient(app)
    resp = client.post("/api/auth/google-session", json={"email": "   "})
    assert resp.status_code == 400


def test_google_login_gis_success():
    """Verify POST /api/auth/google-login validates genuine Google ID token and returns session."""
    client = TestClient(app)
    mock_idinfo = {
        "iss": "accounts.google.com",
        "email": "external.developer@gmail.com",
        "name": "Alex Mercer",
        "picture": "https://lh3.googleusercontent.com/avatar.jpg",
        "sub": "google_uid_10928301"
    }
    with patch("src.ui.app.google_id_token.verify_oauth2_token", return_value=mock_idinfo), \
         patch("src.ui.app.ALLOWED_DOMAINS", []), \
         patch("src.ui.app.ALLOWED_USERS", []):
        resp = client.post("/api/auth/google-login", json={"credential": "mock_google_signed_jwt"})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["token"].startswith("google_")
        assert data["user"]["email"] == "external.developer@gmail.com"
        assert data["user"]["google_name"] == "Alex Mercer"
        assert data["user"]["name"] == "Sarah Jenkins"

        # Test switching persona to David Chen with the Google session token
        me_resp = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {data['token']}", "X-Apex-Persona": "auditor"}
        )
        assert me_resp.status_code == 200
        assert me_resp.json()["user"]["name"] == "David Chen"
        assert me_resp.json()["user"]["persona_type"] == "auditor"


def test_google_login_gis_invalid_token():
    """Verify POST /api/auth/google-login rejects invalid or expired tokens."""
    client = TestClient(app)
    with patch("src.ui.app.google_id_token.verify_oauth2_token", side_effect=ValueError("Token expired")):
        resp = client.post("/api/auth/google-login", json={"credential": "expired_jwt"})
        assert resp.status_code == 401
        assert "Token expired" in resp.json()["detail"]


def test_google_login_gis_empty_credential():
    """Verify POST /api/auth/google-login rejects empty credential."""
    client = TestClient(app)
    resp = client.post("/api/auth/google-login", json={"credential": ""})
    assert resp.status_code == 400


