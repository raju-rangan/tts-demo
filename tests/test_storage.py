"""Unit tests for GCS Storage Client: Bucket naming, prefix routing, and lifecycle rules."""
import re
import os
import tempfile
from unittest.mock import MagicMock
import pytest
from src.storage.gcs_client import GCSStorageClient
from src.ai.personas import PERSONAS

def test_generate_bucket_name():
    """Verify bucket name adheres to GCS naming rules with random 5-char suffix."""
    name1 = GCSStorageClient.generate_bucket_name("tts-bank-audio")
    name2 = GCSStorageClient.generate_bucket_name("tts-bank-audio")

    # Pattern: base-name + 5 lowercase alphanumeric characters
    assert re.match(r"^tts-bank-audio-[a-z0-9]{5}$", name1)
    assert re.match(r"^tts-bank-audio-[a-z0-9]{5}$", name2)
    # Random suffix should vary
    assert name1 != name2

def test_generate_bucket_name_sanitization():
    """Verify non-standard characters in base name are sanitized."""
    raw_name = "My_Bank_Audio_Test!"
    sanitized = GCSStorageClient.generate_bucket_name(raw_name)
    assert re.match(r"^my-bank-audio-test-[a-z0-9]{5}$", sanitized)

def test_prefix_routing_for_all_personas():
    """Verify each financial persona routes to the correct audience prefix key."""
    expected_mappings = {
        "Retail Banking Guide": "external/audio",
        "Wealth & Market Advisor": "external/audio",
        "Regulatory & Policy Officer": "internal/audio",
        "Employee Enablement & Operations": "internal/audio",
        "Fraud & Security Alert": "shared/audio",
    }

    for persona_name, expected_prefix in expected_mappings.items():
        assert persona_name in PERSONAS
        actual_prefix = GCSStorageClient.get_prefix_for_persona(persona_name=persona_name)
        assert actual_prefix == expected_prefix, f"Failed for persona {persona_name}"

def test_prefix_routing_audience_direct():
    """Verify direct audience values map to appropriate prefix keys."""
    assert GCSStorageClient.get_prefix_for_persona(audience="External Customers") == "external/audio"
    assert GCSStorageClient.get_prefix_for_persona(audience="Internal Employees") == "internal/audio"
    assert GCSStorageClient.get_prefix_for_persona(audience="Both") == "shared/audio"
    assert GCSStorageClient.get_prefix_for_persona(audience="Unknown") == "external/audio"

def test_iam_condition_generation():
    """Verify CEL IAM condition expressions contain proper prefix strings."""
    bucket_name = "test-bucket-12345"
    conditions = GCSStorageClient.get_iam_condition_examples(bucket_name)

    assert "external_public" in conditions
    assert f"projects/_/buckets/{bucket_name}/objects/external/" in conditions["external_public"]
    assert f"projects/_/buckets/{bucket_name}/objects/internal/" in conditions["internal_restricted"]
    assert f"projects/_/buckets/{bucket_name}/objects/shared/" in conditions["shared_alerts"]

def test_lifecycle_rule_with_expiration():
    """Verify lifecycle rule adds Delete rule when expiration_days > 0."""
    client = GCSStorageClient(bucket_name="mock-bucket")
    mock_bucket = MagicMock()
    mock_bucket.name = "mock-bucket"
    mock_bucket.lifecycle_rules = []

    updated_rules = client.apply_lifecycle_rule(mock_bucket, expiration_days=30)
    assert len(updated_rules) == 1
    assert updated_rules[0]["action"]["type"] == "Delete"
    assert updated_rules[0]["condition"]["age"] == 30
    mock_bucket.patch.assert_called_once()

def test_lifecycle_rule_zero_expiration():
    """Verify lifecycle rule removes Delete rule when expiration_days == 0."""
    client = GCSStorageClient(bucket_name="mock-bucket")
    mock_bucket = MagicMock()
    mock_bucket.name = "mock-bucket"
    # Pre-existing delete rule
    mock_bucket.lifecycle_rules = [
        {"action": {"type": "Delete"}, "condition": {"age": 30}},
        {"action": {"type": "SetStorageClass"}, "condition": {"age": 90}}
    ]

    updated_rules = client.apply_lifecycle_rule(mock_bucket, expiration_days=0)
    # The Delete rule should be removed, leaving only SetStorageClass
    assert len(updated_rules) == 1
    assert updated_rules[0]["action"]["type"] == "SetStorageClass"
    mock_bucket.patch.assert_called_once()

def test_save_bucket_name_to_env():
    """Verify updating .env file with GCS_BUCKET_NAME."""
    with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
        tf.write("GCP_PROJECT_ID=test-proj\nGCS_BUCKET_NAME=\nAUDIO_RATE=24000\n")
        temp_env = tf.name

    try:
        success = GCSStorageClient.save_bucket_name_to_env("test-bucket-abc12", env_path=temp_env)
        assert success is True

        with open(temp_env, "r") as f:
            content = f.read()

        assert "GCS_BUCKET_NAME=test-bucket-abc12\n" in content
        assert "GCP_PROJECT_ID=test-proj\n" in content
    finally:
        if os.path.exists(temp_env):
            os.remove(temp_env)
