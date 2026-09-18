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
