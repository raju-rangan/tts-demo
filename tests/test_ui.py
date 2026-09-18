"""Integration tests for FastAPI Web Application & API Endpoints."""
import pytest
from fastapi.testclient import TestClient
from src.ui.app import app

@pytest.fixture
def client():
    return TestClient(app)

def test_index_page(client):
    """Verify root path serves the single page application HTML."""
    response = client.get("/")
    assert response.status_code == 200
    assert "Apex" in response.text or "Knowledge" in response.text

def test_auth_login_success(client):
    """Verify demo banking login returns session token and user info."""
    payload = {
        "email": "admin@apexbank.com",
        "password": "demo1234"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert data["user"]["email"] == "admin@apexbank.com"
    assert data["user"]["name"] == "Sarah Jenkins"

def test_auth_login_invalid(client):
    """Verify incorrect credentials return 401 unauthorized."""
    payload = {
        "email": "admin@apexbank.com",
        "password": "wrongpassword"
    }
    response = client.post("/api/auth/login", json=payload)
    assert response.status_code == 401

def test_get_personas_public(client):
    """Verify personas endpoint returns all 5 banking personas."""
    response = client.get("/api/personas")
    assert response.status_code == 200
    personas = response.json()
    assert len(personas) == 5
    names = [p["name"] for p in personas]
    assert "Retail Banking Guide" in names
    assert "Fraud & Security Alert" in names

def test_protected_endpoints_require_auth(client):
    """Verify /api/jobs and /api/stats reject unauthenticated requests."""
    r1 = client.get("/api/jobs")
    assert r1.status_code == 401

    r2 = client.get("/api/stats")
    assert r2.status_code == 401

def test_authenticated_jobs_and_stats(client):
    """Verify authenticated user can list jobs and fetch KPI statistics."""
    # 1. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. List Jobs
    jobs_resp = client.get("/api/jobs", headers=headers)
    assert jobs_resp.status_code == 200
    jobs = jobs_resp.json()
    assert isinstance(jobs, list)
    assert len(jobs) >= 2 # Pre-seeded jobs

    # 3. Get Stats
    stats_resp = client.get("/api/stats", headers=headers)
    assert stats_resp.status_code == 200
    stats = stats_resp.json()
    assert stats["total_jobs"] >= 2
    assert "avg_quality_score" in stats
    assert "total_cost_usd" in stats

def test_stream_audio_isolation(client):
    """Verify failed/running/unknown jobs do not leak or cross-contaminate audio."""
    # 1. Non-existent job
    r_unknown = client.get("/api/audio/job_non_existent")
    assert r_unknown.status_code == 404

    # 2. Failed job in database (job_d9a7b82a)
    r_failed = client.get("/api/audio/job_d9a7b82a")
    assert r_failed.status_code == 404
    assert "Audio unavailable" in r_failed.json()["detail"]

    # 3. Seeded completed job
    r_ok = client.get("/api/audio/job_757eac1a")
    assert r_ok.status_code == 200
    assert r_ok.headers["content-type"] == "audio/mpeg"

def test_get_job_detail(client):
    """Verify single job detail returns overall reasoning and rubric metrics."""
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/jobs/job_757eac1a", headers=headers)
    assert resp.status_code == 200
    job = resp.json()
    assert job["job_id"] == "job_757eac1a"
    assert job["overall_score"] == 4.64
    assert job["overall_reasoning"] is not None
    assert "script_adherence_and_accuracy" in job["rubric_metrics"]
    assert len(job["rubric_metrics"]) == 6

def test_delete_job_api(client):
    """Verify authenticated user can delete a job, and non-existent job returns 404."""
    # 1. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Create a temporary job directly in repository
    from src.db.repository import get_job_repository
    from src.db.models import JobRecord
    repo = get_job_repository()
    temp_job = JobRecord(
        job_id="job_api_delete_test",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Delete API test",
        word_count=3,
        char_count=15,
        gcs_uri="gs://test-bucket/pending/job_api_delete_test",
        status="FAILED"
    )
    repo.save_job(temp_job)

    # 3. Delete job via API
    del_resp = client.delete("/api/jobs/job_api_delete_test", headers=headers)
    assert del_resp.status_code == 200
    assert del_resp.json()["success"] is True

    # 4. Verify job is gone
    get_resp = client.get("/api/jobs/job_api_delete_test", headers=headers)
    assert get_resp.status_code == 404

    # 5. Deleting non-existent job returns 404
    del_again = client.delete("/api/jobs/job_api_delete_test", headers=headers)
    assert del_again.status_code == 404

def test_get_logs_api(client):
    """Verify authenticated user can fetch recent logs."""
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/logs?lines=20", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "logs" in data
    assert isinstance(data["logs"], str)


def test_retry_job_api(client, monkeypatch):
    """Verify authenticated user can retry a job, and non-existent job returns 404."""
    # 1. Unauthenticated retry returns 401
    resp_unauth = client.post("/api/jobs/job_some_id/retry")
    assert resp_unauth.status_code == 401

    # 2. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Retrying non-existent job returns 404
    resp_404 = client.post("/api/jobs/job_non_existent/retry", headers=headers)
    assert resp_404.status_code == 404

    # 4. Create a failed test job directly in repository
    from src.db.repository import get_job_repository
    from src.db.models import JobRecord
    repo = get_job_repository()
    failed_job = JobRecord(
        job_id="job_api_retry_test",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Retry API test article text",
        word_count=5,
        char_count=27,
        gcs_uri="gs://test-bucket/pending/job_api_retry_test",
        status="FAILED",
        error_message="Previous error that should be cleared"
    )
    repo.save_job(failed_job)

    # Mock _execute_async_synthesis so background task doesn't make real network calls
    executed_jobs = []
    def mock_execute(job_id, text, persona_name, run_judge, title, voice_customization=None, **kwargs):
        executed_jobs.append((job_id, voice_customization))
    monkeypatch.setattr("src.ui.app._execute_async_synthesis", mock_execute)

    # 5. Retry job via API
    retry_resp = client.post("/api/jobs/job_api_retry_test/retry", headers=headers)
    assert retry_resp.status_code == 200
    data = retry_resp.json()
    assert data["status"] == "RUNNING"
    assert data["job_id"] == "job_api_retry_test"
    assert data["job"]["error_message"] is None
    assert data["job"]["status"] == "RUNNING"

    # Verify background task was scheduled
    assert len(executed_jobs) == 1
    assert executed_jobs[0][0] == "job_api_retry_test"

    # Verify record in repo was updated to RUNNING and error cleared
    updated = repo.get_job("job_api_retry_test")
    assert updated.status == "RUNNING"
    assert updated.error_message is None

    # Clean up test artifact from database
    repo.delete_job("job_api_retry_test")


def test_create_job_with_voice_customization(client, monkeypatch):
    """Verify create job endpoint accepts and stores voice_customization."""
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    executed_jobs = []
    def mock_execute(job_id, text, persona_name, run_judge, title, voice_customization=None, **kwargs):
        executed_jobs.append((job_id, voice_customization))
    monkeypatch.setattr("src.ui.app._execute_async_synthesis", mock_execute)

    payload = {
        "text": "This is a comprehensive financial guide on wealth management and estate planning.",
        "persona": "Wealth & Market Advisor",
        "title": "Wealth Guide",
        "voice_customization": "Authoritative yet approachable, measured cadence on risk metrics."
    }

    resp = client.post("/api/jobs", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    job_id = data["job_id"]
    assert data["job"]["voice_customization"] == "Authoritative yet approachable, measured cadence on risk metrics."
    assert data["job"]["progress_stage"] == "CHUNKING"

    from src.db.repository import get_job_repository
    repo = get_job_repository()
    stored_job = repo.get_job(job_id)
    assert stored_job is not None
    assert stored_job.voice_customization == "Authoritative yet approachable, measured cadence on risk metrics."

    # Test update_job_progress
    repo.update_job_progress(
        job_id=job_id,
        progress_stage="SYNTHESIZING",
        progress_message="Synthesizing turn 1 of 2...",
        current_turn=1,
        total_turns=2
    )
    progress_job = repo.get_job(job_id)
    assert progress_job.progress_stage == "SYNTHESIZING"
    assert progress_job.progress_message == "Synthesizing turn 1 of 2..."
    assert progress_job.current_turn == 1
    assert progress_job.total_turns == 2

    # Clean up
    repo.delete_job(job_id)


def test_create_bulk_jobs_api_validation(client):
    """Verify validation for POST /api/jobs/bulk (empty list, invalid URLs)."""
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Empty URLs
    resp = client.post("/api/jobs/bulk", json={"urls": [], "persona": "Retail Banking Guide"}, headers=headers)
    assert resp.status_code == 422 or resp.status_code == 400

    # All invalid URLs
    resp = client.post("/api/jobs/bulk", json={"urls": ["not_a_url", "ftp://example.com"], "persona": "Retail Banking Guide"}, headers=headers)
    assert resp.status_code == 400
    assert "No valid HTTP/HTTPS URLs found" in resp.json()["detail"]


def test_create_bulk_jobs_api_success(client):
    """Verify bulk job creation pre-creates JobRecords and enqueues background worker."""
    from unittest.mock import patch

    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "urls": [
            "https://apexbank.com/wealth/q4-outlook",
            "https://apexbank.com/retail/hysa-explained",
            "not_valid_url"
        ],
        "persona": "Wealth & Market Advisor",
        "voice_customization": "Calm, analytical pace.",
        "run_judge": False
    }

    with patch("src.ui.app._execute_bulk_url_processing"):
        resp = client.post("/api/jobs/bulk", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enqueued"
        assert data["total_enqueued"] == 2
        assert "not_valid_url" in data["invalid_urls"]
        assert len(data["jobs"]) == 2

        job_ids = [j["job_id"] for j in data["jobs"]]
        from src.db.repository import get_job_repository
        repo = get_job_repository()
        for jid in job_ids:
            job = repo.get_job(jid)
            assert job is not None
            assert job.persona == "Wealth & Market Advisor"
            assert job.voice_customization == "Calm, analytical pace."
            assert job.source_url.startswith("https://apexbank.com/")
            assert job.progress_stage == "QUEUED"
            repo.delete_job(jid)


def test_execute_bulk_url_processing_worker():
    """Verify background worker extracts URLs sequentially and invokes synthesis."""
    from unittest.mock import patch
    from src.ui.app import _execute_bulk_url_processing
    from src.utils.extractor import ExtractedArticle
    from src.db.repository import get_job_repository

    repo = get_job_repository()
    jid = "job_test_bulk_worker"
    items = [{"job_id": jid, "url": "https://apexbank.com/test-article"}]

    mock_article = ExtractedArticle(
        url="https://apexbank.com/test-article",
        title="Test Article Title",
        text="This is an extracted article body with sufficient words for processing.",
        word_count=11,
        char_count=70
    )

    with patch("src.ui.app.extract_article_from_url", return_value=mock_article) as mock_extract, \
         patch("src.ui.app._execute_async_synthesis") as mock_synth:
        
        _execute_bulk_url_processing(
            job_items=items,
            persona_name="Retail Banking Guide",
            run_judge=False
        )

        assert mock_extract.called
        assert mock_synth.called
        mock_synth.assert_called_with(
            job_id=jid,
            text=mock_article.text,
            persona_name="Retail Banking Guide",
            run_judge=False,
            title=mock_article.title,
            voice_customization=None,
            source_url="https://apexbank.com/test-article"
        )
        repo.delete_job(jid)


def test_html_modal_nesting_and_structure(client):
    """Ensure HTML template has balanced tags and newJobModal is an independent sibling of jobDetailModal."""
    from html.parser import HTMLParser
    
    response = client.get("/")
    assert response.status_code == 200
    html_content = response.text

    class DOMTracker(HTMLParser):
        def __init__(self):
            super().__init__()
            self.stack = []
            self.void_tags = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
            self.modal_parent_of_new = None
            self.modal_parent_of_bulk = None
            self.found_new_modal = False
            self.found_bulk_modal = False

        def handle_starttag(self, tag, attrs):
            if tag not in self.void_tags:
                tag_id = dict(attrs).get('id', '')
                if tag_id == 'newJobModal':
                    self.found_new_modal = True
                    active_ids = [item[2] for item in self.stack]
                    self.modal_parent_of_new = 'jobDetailModal' in active_ids
                elif tag_id == 'bulkJobModal':
                    self.found_bulk_modal = True
                    active_ids = [item[2] for item in self.stack]
                    self.modal_parent_of_bulk = ('jobDetailModal' in active_ids or 'newJobModal' in active_ids)
                self.stack.append((tag, self.getpos(), tag_id))

        def handle_endtag(self, tag):
            if tag in self.void_tags:
                return
            if self.stack:
                last_tag, pos, tag_id = self.stack.pop()
                assert last_tag == tag, f"Mismatched tag: expected </{last_tag}> (line {pos[0]} id={tag_id}), got </{tag}>"

    tracker = DOMTracker()
    tracker.feed(html_content)
    assert len(tracker.stack) == 0, f"Unclosed tags remaining: {tracker.stack}"
    assert tracker.found_new_modal is True, "newJobModal must exist in DOM"
    assert tracker.found_bulk_modal is True, "bulkJobModal must exist in DOM"
    assert tracker.modal_parent_of_new is False, "newJobModal must NOT be nested inside jobDetailModal"
    assert tracker.modal_parent_of_bulk is False, "bulkJobModal must NOT be nested inside other modals"
