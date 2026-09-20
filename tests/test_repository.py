"""Unit tests for Job Repository & Cost Telemetry Engine."""
import os
import pytest
from src.db.models import JobRecord, TokenUsageDetails, CostBreakdown
from src.db.repository import SQLiteJobRepository, get_job_repository
from src.ai.cost_calculator import TokenCostCalculator

@pytest.fixture
def temp_repo(tmp_path):
    db_file = os.path.join(tmp_path, "test_jobs.db")
    return SQLiteJobRepository(db_path=db_file)

def test_save_and_retrieve_job(temp_repo):
    job = JobRecord(
        job_id="job_test001",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        article_title="Test Banking Savings",
        transcript="Test savings article content.",
        word_count=4,
        char_count=28,
        gcs_uri="gs://test-bucket/external/audio/job_test001.mp3",
        overall_score=4.5,
        passed_rubric=True,
        status="COMPLETED"
    )
    temp_repo.save_job(job)

    retrieved = temp_repo.get_job("job_test001")
    assert retrieved is not None
    assert retrieved.job_id == "job_test001"
    assert retrieved.persona == "Retail Banking Guide"
    assert retrieved.overall_score == 4.5
    assert retrieved.passed_rubric is True

def test_list_jobs_and_persona_filter(temp_repo):
    job1 = JobRecord(
        job_id="job_filter_1",
        persona="Wealth & Market Advisor",
        audience="External Customers",
        voice_name="Charon",
        transcript="Wealth transcript",
        word_count=2,
        char_count=17,
        gcs_uri="gs://test-bucket/external/audio/job_filter_1.mp3"
    )
    job2 = JobRecord(
        job_id="job_filter_2",
        persona="Regulatory & Policy Officer",
        audience="Internal Employees",
        voice_name="Kore",
        transcript="Policy transcript",
        word_count=2,
        char_count=17,
        gcs_uri="gs://test-bucket/internal/audio/job_filter_2.mp3"
    )
    temp_repo.save_job(job1)
    temp_repo.save_job(job2)

    all_jobs = temp_repo.list_jobs()
    assert len(all_jobs) == 2

    wealth_jobs = temp_repo.list_jobs(persona="Wealth & Market Advisor")
    assert len(wealth_jobs) == 1
    assert wealth_jobs[0].job_id == "job_filter_1"

def test_token_cost_calculator():
    sample_text = "This is a sample banking article with ten words in total."
    duration_sec = 60.0

    tokens, cost = TokenCostCalculator.calculate_pipeline_cost(
        text=sample_text,
        duration_seconds=duration_sec,
        tts_model="gemini-3.1-flash-tts-preview",
        judge_model="gemini-3.8-flash"
    )

    assert tokens.input_text_tokens > 0
    assert tokens.audio_output_tokens > 0
    assert tokens.total_tokens > 0
    assert cost.tts_cost_usd > 0.0
    assert cost.judge_cost_usd > 0.0
    assert cost.total_cost_usd == pytest.approx(cost.tts_cost_usd + cost.judge_cost_usd, rel=1e-5)

def test_delete_job(temp_repo):
    job = JobRecord(
        job_id="job_to_delete",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Test content",
        word_count=2,
        char_count=12,
        gcs_uri="gs://test-bucket/external/audio/job_to_delete.mp3"
    )
    temp_repo.save_job(job)
    assert temp_repo.get_job("job_to_delete") is not None

    deleted = temp_repo.delete_job("job_to_delete")
    assert deleted is True
    assert temp_repo.get_job("job_to_delete") is None

    # Deleting non-existent job returns False
    assert temp_repo.delete_job("job_to_delete") is False

def test_firestore_repository_mock_operations(monkeypatch):
    """Test FirestoreJobRepository CRUD operations with a mocked Firestore Client."""
    from unittest.mock import MagicMock
    from src.db.repository import FirestoreJobRepository
    import sys

    # Mock google.cloud.firestore
    mock_firestore = MagicMock()
    mock_client = MagicMock()
    mock_firestore.Client.return_value = mock_client
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", mock_firestore)

    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection

    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref

    repo = FirestoreJobRepository(project_id="test-proj", collection_name="tts_jobs", database_name="tts-jobs")
    mock_firestore.Client.assert_called_with(project="test-proj", database="tts-jobs")

    job = JobRecord(
        job_id="fs_test_1",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="FS test transcript",
        word_count=3,
        char_count=18,
        gcs_uri="gs://test-bucket/external/audio/fs_test_1.mp3"
    )

    # Test save
    repo.save_job(job)
    mock_collection.document.assert_called_with("fs_test_1")
    mock_doc_ref.set.assert_called_once()

    # Test get existing
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict.return_value = job.model_dump()
    mock_doc_ref.get.return_value = mock_snapshot

    retrieved = repo.get_job("fs_test_1")
    assert retrieved is not None
    assert retrieved.job_id == "fs_test_1"

    # Test delete
    deleted = repo.delete_job("fs_test_1")
    assert deleted is True
    mock_doc_ref.delete.assert_called_once()


def test_sqlite_user_tour_status_lifecycle(temp_repo):
    """Verify SQLite tracking of onboarding tour keyed per Google identity per persona (google_email, persona)."""
    google_user_1 = "alex.morgan@apexbank.com"
    # 1. New Google user has not seen tour for either creator or auditor
    assert temp_repo.get_user_tour_status(google_user_1, "creator") is False
    assert temp_repo.get_user_tour_status(google_user_1, "auditor") is False

    # 2. Mark tour as completed/dismissed for Google user 1 in Creator view
    temp_repo.set_user_tour_dismissed(google_user_1, "creator", dismissed=True)
    assert temp_repo.get_user_tour_status(google_user_1, "creator") is True
    # Auditor view tour MUST remain unseen (False)
    assert temp_repo.get_user_tour_status(google_user_1, "auditor") is False

    # 3. Mark tour as completed/dismissed for Google user 1 in Auditor view
    temp_repo.set_user_tour_dismissed(google_user_1, "auditor", dismissed=True)
    assert temp_repo.get_user_tour_status(google_user_1, "creator") is True
    assert temp_repo.get_user_tour_status(google_user_1, "auditor") is True

    # 4. Independent tracking across distinct Google accounts (e.g. Rachel vs Alex)
    google_user_2 = "rachel.lee@apexbank.com"
    assert temp_repo.get_user_tour_status(google_user_2, "creator") is False
    assert temp_repo.get_user_tour_status(google_user_2, "auditor") is False

    # 5. Reset all tour tracking
    temp_repo.reset_all_tour_tracking()
    assert temp_repo.get_user_tour_status(google_user_1, "creator") is False
    assert temp_repo.get_user_tour_status(google_user_1, "auditor") is False
    assert temp_repo.get_user_tour_status(google_user_2, "creator") is False


def test_firestore_user_tour_status_lifecycle(monkeypatch):
    """Verify Firestore repository tracking of (google_email, persona) composite preferences document."""
    from unittest.mock import MagicMock
    from src.db.repository import FirestoreJobRepository
    import sys

    mock_firestore = MagicMock()
    mock_client = MagicMock()
    mock_firestore.Client.return_value = mock_client
    monkeypatch.setitem(sys.modules, "google.cloud.firestore", mock_firestore)

    mock_collection = MagicMock()
    mock_client.collection.return_value = mock_collection

    mock_doc_ref = MagicMock()
    mock_collection.document.return_value = mock_doc_ref

    repo = FirestoreJobRepository(project_id="test-proj", collection_name="tts_jobs", database_name="tts-jobs")

    google_email = "alex.morgan@apexbank.com"

    # 1. Mock get when doc does not exist
    mock_snap_empty = MagicMock()
    mock_snap_empty.exists = False
    mock_doc_ref.get.return_value = mock_snap_empty
    assert repo.get_user_tour_status(google_email, "creator") is False
    mock_collection.document.assert_called_with(f"{google_email}__creator")

    # 2. Mock set dismissal
    repo.set_user_tour_dismissed(google_email, "creator", dismissed=True)
    mock_collection.document.assert_called_with(f"{google_email}__creator")
    mock_doc_ref.set.assert_called_once()

    # 3. Mock get when doc exists with has_seen_tour = True
    mock_snap_seen = MagicMock()
    mock_snap_seen.exists = True
    mock_snap_seen.to_dict.return_value = {"has_seen_tour": True, "google_email": google_email, "persona": "creator"}
    mock_doc_ref.get.return_value = mock_snap_seen
    assert repo.get_user_tour_status(google_email, "creator") is True

    # 4. Test reset_all_tour_tracking
    mock_doc_1 = MagicMock()
    mock_collection.stream.return_value = [mock_doc_1]
    repo.reset_all_tour_tracking()
    mock_doc_1.reference.delete.assert_called_once()


def test_job_speed_persistence_and_defaults(temp_repo):
    """Verify speed field is correctly persisted and defaults to 1.0."""
    # 1. Custom speed
    job_speedy = JobRecord(
        job_id="job_speed_001",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Fast speech delivery test",
        word_count=4,
        char_count=25,
        gcs_uri="gs://test-bucket/external/audio/job_speed_001.mp3",
        speed=1.25
    )
    temp_repo.save_job(job_speedy)

    retrieved = temp_repo.get_job("job_speed_001")
    assert retrieved is not None
    assert retrieved.speed == 1.25

    # 2. Default speed
    job_default = JobRecord(
        job_id="job_speed_002",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Default speech delivery test",
        word_count=4,
        char_count=28,
        gcs_uri="gs://test-bucket/external/audio/job_speed_002.mp3"
    )
    temp_repo.save_job(job_default)
    retrieved_def = temp_repo.get_job("job_speed_002")
    assert retrieved_def is not None
    assert retrieved_def.speed == 1.0


def test_job_retry_telemetry_persistence(temp_repo):
    """Verify retry_count, remediation_prompt, and previous_attempt_score roundtrip through SQLite."""
    # 1. Job with retry metadata
    job_retried = JobRecord(
        job_id="job_retry_001",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Test retry persistence transcript.",
        word_count=5,
        char_count=36,
        gcs_uri="gs://test-bucket/external/audio/job_retry_001.mp3",
        retry_count=1,
        remediation_prompt="WHAT YOU DID INCORRECTLY: Skipped main title.\nMAKE IT RIGHT: Read the title clearly.",
        previous_attempt_score=3.2
    )
    temp_repo.save_job(job_retried)

    retrieved = temp_repo.get_job("job_retry_001")
    assert retrieved is not None
    assert retrieved.retry_count == 1
    assert "Skipped main title" in retrieved.remediation_prompt
    assert retrieved.previous_attempt_score == 3.2

    # 2. Defaults for unretried job
    job_fresh = JobRecord(
        job_id="job_retry_002",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Fresh job without retries.",
        word_count=5,
        char_count=27,
        gcs_uri="gs://test-bucket/external/audio/job_retry_002.mp3"
    )
    temp_repo.save_job(job_fresh)

    retrieved_fresh = temp_repo.get_job("job_retry_002")
    assert retrieved_fresh is not None
    assert retrieved_fresh.retry_count == 0
    assert retrieved_fresh.remediation_prompt is None
    assert retrieved_fresh.previous_attempt_score is None


