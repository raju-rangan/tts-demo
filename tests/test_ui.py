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
    """Verify personas endpoint returns all banking and podcast personas."""
    response = client.get("/api/personas")
    assert response.status_code == 200
    personas = response.json()
    assert len(personas) >= 8
    names = [p["name"] for p in personas]
    assert "Retail Banking Guide" in names
    assert "Fraud & Security Alert" in names
    assert "Podcast: Co-Hosts (Man & Woman)" in names
    assert "Podcast: Co-Hosts (Man & Man)" in names
    assert "Podcast: Co-Hosts (Woman & Woman)" in names

    # Verify podcast metadata
    podcast = next(p for p in personas if p["name"] == "Podcast: Co-Hosts (Man & Woman)")
    assert podcast["is_podcast"] is True
    assert len(podcast["speakers"]) == 2

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
    assert "pass_rate" in stats
    assert "audited_count" in stats
    assert "compliant_count" in stats
    assert "flagged_count" in stats
    assert "cost_breakdown" in stats
    assert "tts_cost_usd" in stats["cost_breakdown"]
    assert "judge_cost_usd" in stats["cost_breakdown"]
    assert "token_breakdown" in stats
    assert "input_text_tokens" in stats["token_breakdown"]
    assert "rubric_averages" in stats
    assert "script_adherence_and_accuracy" in stats["rubric_averages"]
    assert "model_matrix" in stats
    assert len(stats["model_matrix"]) >= 2
    for m_name, m_data in stats["model_matrix"].items():
        assert "input_tokens" in m_data
        assert "output_tokens" in m_data
        assert "total_tokens" in m_data
        assert "total_cost_usd" in m_data
        assert "role" in m_data
        assert "input_pricing" in m_data
        assert "output_pricing" in m_data
        assert m_data["total_tokens"] == m_data["input_tokens"] + m_data["output_tokens"]

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
            speed=1.0,
            source_url="https://apexbank.com/test-article",
            created_by=None
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


def test_home_hub_and_auditor_view(client):
    """Verify Home Hub navigation, persona sections, and compliance elements in the UI."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Home Hub / Profile Select Screen
    assert 'id="profileSelectSection"' in html
    assert "Select Workspace Persona" in html
    assert "Enter as Content Creator" in html
    assert "Enter as Compliance Auditor" in html

    # Top Navigation Switch Persona Button
    assert "Switch Persona" in html
    assert 'onclick="showProfileSelect()"' in html

    # Creator Studio Section
    assert 'id="creatorStudioSection"' in html
    assert 'id="btnNavNewJob"' in html
    assert 'id="btnNavBulk"' in html

    # Compliance Auditor Console Section
    assert 'id="auditorConsoleSection"' in html
    assert 'id="auditorModeBanner"' in html
    assert 'id="btnNavFinOps"' in html
    assert 'id="kpiPassRate"' in html
    assert 'id="kpiAuditedDisclosures"' in html
    assert 'id="kpiFlaggedItems"' in html
    assert 'id="kpiAuditorCost"' in html

    # Compliance Filter Tabs
    assert 'id="complianceFilterTabs"' in html
    assert 'setComplianceFilter(' in html

def test_finops_and_compliance_drawer_elements(client):
    """Verify FinOps & Compliance Governance drawer structure and interactive controls."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Drawer Container & Header
    assert 'id="finOpsDrawer"' in html
    assert "FinOps & Compliance Governance" in html
    assert "Auditor Console" in html
    assert 'onclick="closeFinOpsDrawer()"' in html
    assert 'onclick="refreshFinOpsData()"' in html

    # 2. Top-Line KPI Cards
    assert 'id="foTotalCost"' in html
    assert 'id="foTtsCostSplit"' in html
    assert 'id="foTotalTokens"' in html
    assert 'id="foTokenBreakdown"' in html
    assert 'id="foPassRate"' in html
    assert 'id="foPassCounts"' in html
    assert 'id="foTotalMinutes"' in html

    # 3. Rubric & Persona Containers
    assert 'id="foRubricDimensionList"' in html
    assert 'id="foPersonaTableBody"' in html

    # 4. Unit Economics & Infrastructure
    assert 'id="foCostPerMin"' in html
    assert 'id="foCostPerJob"' in html
    assert 'id="foJudgeCostRatio"' in html
    assert 'id="foBackendRepo"' in html
    assert 'id="foBucketName"' in html

    # 5. Flagged Disclosures Container
    assert 'id="foFlaggedContainer"' in html
    assert 'id="foFlaggedHeaderCount"' in html

    # 6. JavaScript functions wired
    assert "function openFinOpsDrawer()" in html
    assert "function closeFinOpsDrawer()" in html
    assert "function refreshFinOpsData()" in html
    assert "function renderFinOpsDrawer(" in html


def test_auditor_full_page_dashboard_and_charts(client):
    """Verify full-page Auditor Governance Dashboard, Chart.js canvases, sub-nav, and analytics widgets."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Chart.js CDN script inclusion
    assert "cdn.jsdelivr.net/npm/chart.js" in html

    # 2. Auditor Sub-Navigation
    assert 'id="auditorSubNav"' in html
    assert 'id="btnAuditorSubDashboard"' in html
    assert 'id="btnAuditorSubRegistry"' in html
    assert "switchAuditorSubView('dashboard')" in html
    assert "switchAuditorSubView('registry')" in html

    # 3. Full-Page Auditor Dashboard Container
    assert 'id="auditorFullDashboard"' in html
    assert 'id="jobDirectorySection"' in html

    # 4. Canvas elements for Chart.js
    assert 'id="chartRubricRadar"' in html
    assert 'id="chartFinopsSplit"' in html
    assert 'id="chartPersonaBars"' in html
    assert 'id="chartTokenStack"' in html

    # 5. Full Dashboard KPI elements
    assert 'id="fullFoTotalCost"' in html
    assert 'id="fullFoPassRate"' in html
    assert 'id="fullFoTotalTokens"' in html
    assert 'id="fullFoTotalMinutes"' in html

    # 6. Persona matrix, unit economics, and action center
    assert 'id="fullFoPersonaTableBody"' in html
    assert 'id="fullFoCostPerMin"' in html
    assert 'id="fullFoCostPerJob"' in html
    assert 'id="fullFoAuditorOverhead"' in html
    assert 'id="fullFoFlaggedContainer"' in html
    assert 'id="fullFoFlaggedBadge"' in html

    # 7. JavaScript controller & chart rendering logic
    assert "function switchAuditorSubView(" in html
    assert "function refreshAuditorDashboard(" in html
    assert "function renderAuditorDashboard(" in html
    assert "function renderAuditorCharts(" in html


def test_localhost_auth_bypass_ui_elements(client):
    """Verify localhost auth bypass elements, badges, and fallback scripts exist in frontend HTML."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="localBypassCard"' in html
    assert 'id="navLocalDevBadge"' in html
    assert "IS_LOCALHOST" in html
    assert "function bypassAuthLocal()" in html
    assert "'local-dev-token'" in html


def test_job_creation_and_modal_progress_resilience(client):
    """Verify frontend HTML has resilient openJobDetail fallback, immediate unshift, and sample text tuning."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # 1. Resilient openJobDetail with direct fetch fallback
    assert "async function openJobDetail(jobId, fallbackJob = null)" in html
    assert "fetch(`/api/jobs/${jobId}`" in html
    assert "ALL_JOBS.unshift(job)" in html

    # 2. Immediate state updates in submitNewJob and submitBulkJobs
    assert "ALL_JOBS.unshift(data.job)" in html
    assert "openJobDetail(data.job_id, data.job)" in html
    assert "openJobDetail(data.jobs[0].job_id, data.jobs[0])" in html

    # 3. Clean error formatting
    assert "Array.isArray(data.detail)" in html
    assert "statusBox.className = 'p-3 rounded-xl bg-rose-950/40" in html

    # 4. Sample text director note tuning
    assert "inputVoiceCustomization" in html
    assert "High-Yield" in html


def test_user_tour_endpoints_lifecycle(client):
    """Verify tour status check, dismissal, and reset lifecycle via API keyed by (google_email, persona)."""
    # 1. Unauthenticated requests must fail with 401
    assert client.get("/api/user/tour-status").status_code == 401
    assert client.post("/api/user/tour-dismiss").status_code == 401
    assert client.post("/api/user/tour-reset").status_code == 401
    assert client.post("/api/user/tour-reset-all").status_code == 401

    # 2. Authenticate session
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Reset tour status to ensure fresh state
    reset_resp = client.post("/api/user/tour-reset", headers=headers)
    assert reset_resp.status_code == 200
    assert reset_resp.json()["has_seen_tour"] is False
    assert reset_resp.json()["tracked_by"] == "google_id_per_persona"

    # 4. Check tour status returns false
    status_resp1 = client.get("/api/user/tour-status", headers=headers)
    assert status_resp1.status_code == 200
    assert status_resp1.json()["has_seen_tour"] is False
    assert status_resp1.json()["google_email"] == "admin@apexbank.com"
    assert status_resp1.json()["tracked_by"] == "google_id_per_persona"

    # 5. Dismiss tour
    dismiss_resp = client.post("/api/user/tour-dismiss", headers=headers)
    assert dismiss_resp.status_code == 200
    assert dismiss_resp.json()["has_seen_tour"] is True
    assert dismiss_resp.json()["google_email"] == "admin@apexbank.com"
    assert dismiss_resp.json()["tracked_by"] == "google_id_per_persona"

    # 6. Check tour status now returns true
    status_resp2 = client.get("/api/user/tour-status", headers=headers)
    assert status_resp2.status_code == 200
    assert status_resp2.json()["has_seen_tour"] is True

    # 7. Reset again
    reset_resp2 = client.post("/api/user/tour-reset", headers=headers)
    assert reset_resp2.status_code == 200
    assert reset_resp2.json()["has_seen_tour"] is False

    status_resp3 = client.get("/api/user/tour-status", headers=headers)
    assert status_resp3.status_code == 200
    assert status_resp3.json()["has_seen_tour"] is False

    # 8. Reset all tours across all users and personas
    reset_all_resp = client.post("/api/user/tour-reset-all", headers=headers)
    assert reset_all_resp.status_code == 200
    assert reset_all_resp.json()["status"] == "all_tours_reset"


def test_tour_tracking_per_google_identity_per_persona(client):
    """Verify tour dismissal is partitioned by (google_email, persona).
    When user@gmail.com logs in:
      - First visit to Creator view prompts tour. Once dismissed, Creator stays dismissed.
      - First visit to Auditor view prompts Auditor tour. Once dismissed, Auditor stays dismissed.
    """
    # 1. Establish Google authenticated session
    google_email = "alex.morgan@apexbank.com"
    session_resp = client.post("/api/auth/google-session", json={"email": google_email})
    assert session_resp.status_code == 200
    token = session_resp.json()["token"]

    creator_headers = {"Authorization": f"Bearer {token}", "X-Apex-Persona": "creator"}
    auditor_headers = {"Authorization": f"Bearer {token}", "X-Apex-Persona": "auditor"}

    # 2. Reset all tour tracking for clean test baseline
    client.post("/api/user/tour-reset-all", headers=creator_headers)

    # 3. Check status as Creator persona: has_seen_tour is False
    st_creator_before = client.get("/api/user/tour-status", headers=creator_headers).json()
    assert st_creator_before["has_seen_tour"] is False
    assert st_creator_before["google_email"] == google_email
    assert st_creator_before["persona"] == "creator"

    # 4. Check status as Auditor persona: has_seen_tour is also False initially
    st_auditor_before = client.get("/api/user/tour-status", headers=auditor_headers).json()
    assert st_auditor_before["has_seen_tour"] is False
    assert st_auditor_before["google_email"] == google_email
    assert st_auditor_before["persona"] == "auditor"

    # 5. Dismiss tour while in Creator persona
    dismiss_creator = client.post("/api/user/tour-dismiss", headers=creator_headers).json()
    assert dismiss_creator["has_seen_tour"] is True
    assert dismiss_creator["google_email"] == google_email
    assert dismiss_creator["persona"] == "creator"
    assert dismiss_creator["tracked_by"] == "google_id_per_persona"

    # 6. Verify Creator status is now True, but Auditor status is STILL False!
    st_creator_after = client.get("/api/user/tour-status", headers=creator_headers).json()
    assert st_creator_after["has_seen_tour"] is True

    st_auditor_still_unseen = client.get("/api/user/tour-status", headers=auditor_headers).json()
    assert st_auditor_still_unseen["has_seen_tour"] is False
    assert st_auditor_still_unseen["persona"] == "auditor"

    # 7. Now switch to Auditor persona and dismiss Auditor tour
    dismiss_auditor = client.post("/api/user/tour-dismiss", headers=auditor_headers).json()
    assert dismiss_auditor["has_seen_tour"] is True
    assert dismiss_auditor["persona"] == "auditor"

    # 8. Both views are now marked as seen for Alex Morgan
    assert client.get("/api/user/tour-status", headers=creator_headers).json()["has_seen_tour"] is True
    assert client.get("/api/user/tour-status", headers=auditor_headers).json()["has_seen_tour"] is True

    # 9. Verify a different Google identity remains unseen for both personas
    session2_resp = client.post("/api/auth/google-session", json={"email": "rachel.lee@apexbank.com"})
    token2 = session2_resp.json()["token"]
    headers2_creator = {"Authorization": f"Bearer {token2}", "X-Apex-Persona": "creator"}
    headers2_auditor = {"Authorization": f"Bearer {token2}", "X-Apex-Persona": "auditor"}

    assert client.get("/api/user/tour-status", headers=headers2_creator).json()["has_seen_tour"] is False
    assert client.get("/api/user/tour-status", headers=headers2_auditor).json()["has_seen_tour"] is False

    # 10. Global reset clears for all users
    client.post("/api/user/tour-reset-all", headers=creator_headers)
    assert client.get("/api/user/tour-status", headers=creator_headers).json()["has_seen_tour"] is False
    assert client.get("/api/user/tour-status", headers=auditor_headers).json()["has_seen_tour"] is False


def test_html_guided_tour_assets_and_elements(client):
    """Verify the single-page HTML contains Driver.js assets, button, and engine functions."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Vendor assets
    assert 'href="/static/vendor/driver.css"' in html
    assert 'src="/static/vendor/driver.js"' in html

    # DOM elements
    assert 'id="btnGuidedTour"' in html
    assert 'id="btnSwitchPersona"' in html
    assert 'driverjs-theme' in html

    # Engine JavaScript functions
    assert "startGuidedTour" in html
    assert "checkAndPromptTour" in html
    assert "recordTourDismissal" in html
    assert "resetTourStatus" in html
    assert "/api/user/tour-status" in html
    assert "/api/user/tour-dismiss" in html


def test_create_job_with_speed_control(client, monkeypatch):
    """Verify /api/jobs accepts speed and persists it in the created job."""
    # 1. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Mock _execute_async_synthesis to prevent live network call
    def mock_execute(*args, **kwargs):
        pass
    monkeypatch.setattr("src.ui.app._execute_async_synthesis", mock_execute)

    # 2. Submit job with custom speed = 1.25
    payload = {
        "text": "This is a detailed retail banking transcript with financial terms.",
        "persona": "Retail Banking Guide",
        "run_judge": False,
        "speed": 1.25
    }
    resp = client.post("/api/jobs", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "job" in data
    assert data["job"]["speed"] == 1.25

    # 3. Verify validation error on out-of-range speed (e.g. 3.0)
    bad_payload = {
        "text": "This is a detailed retail banking transcript with financial terms.",
        "persona": "Retail Banking Guide",
        "run_judge": False,
        "speed": 3.0
    }
    bad_resp = client.post("/api/jobs", json=bad_payload, headers=headers)
    assert bad_resp.status_code == 422


def test_html_speed_control_elements(client):
    """Verify HTML contains speech speed slider, preset buttons, and player playback controls."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="inputSpeed"' in html
    assert 'id="speedValueBadge"' in html
    assert 'id="inputBulkSpeed"' in html
    assert 'id="bulkSpeedValueBadge"' in html
    assert 'id="detailSpeed"' in html
    assert 'playback-rate-btn' in html
    assert 'updateSpeedDisplay' in html
    assert 'setSpeedPreset' in html
    assert 'setPlaybackRate' in html


def test_retry_preview_endpoint(client):
    """Verify GET /api/jobs/{job_id}/retry-preview parses evaluations and generates critique directives."""
    from src.db.repository import get_job_repository
    from src.db.models import JobRecord

    # 1. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. 404 for non-existent job
    resp_404 = client.get("/api/jobs/job_preview_nonexistent/retry-preview", headers=headers)
    assert resp_404.status_code == 404

    # 3. Create job with low scoring evaluation
    repo = get_job_repository()
    job = JobRecord(
        job_id="job_preview_test_1",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Apex Bank CD rates with FDIC insurance.",
        word_count=7,
        char_count=42,
        gcs_uri="gs://test-bucket/pending/job_preview_test_1.mp3",
        status="COMPLETED",
        overall_score=3.2,
        passed_rubric=False,
        rubric_metrics={
            "Script Adherence And Accuracy": {
                "score": 2.0,
                "passed": False,
                "reasoning": "Skipped the introductory title and omitted parenthetical '(FDIC)'."
            },
            "Tone Consistency": {
                "score": 4.5,
                "passed": True,
                "reasoning": "Professional and clear delivery."
            }
        },
        overall_reasoning="Good tone but failed verbatim accuracy requirements.",
        actionable_feedback=["Ensure the full title is spoken aloud and all abbreviations are pronounced."]
    )
    repo.save_job(job)

    try:
        # 4. Request preview
        resp = client.get("/api/jobs/job_preview_test_1/retry-preview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job_id"] == "job_preview_test_1"
        assert data["overall_score"] == 3.2
        assert len(data["flagged_metrics"]) == 1
        assert data["flagged_metrics"][0]["label"] == "Script Adherence & Verbatim Accuracy"
        assert data["flagged_metrics"][0]["score"] == 2.0
        assert "PREVIOUS TAKE AUDITOR ASSESSMENT" in data["suggested_directive"]
        assert "Skipped the introductory title" in data["suggested_directive"]
        assert "Ensure the full title is spoken aloud" in data["suggested_directive"]
    finally:
        repo.delete_job("job_preview_test_1")


def test_retry_job_with_critique_injection(client, monkeypatch):
    """Verify POST /api/jobs/{job_id}/retry accepts RetryJobRequest, increments retry_count, and injects critique."""
    from src.db.repository import get_job_repository
    from src.db.models import JobRecord

    # 1. Login
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Setup job in repo
    repo = get_job_repository()
    job = JobRecord(
        job_id="job_critic_retry_exec_test",
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        transcript="Test retry critique execution.",
        word_count=4,
        char_count=30,
        gcs_uri="gs://test-bucket/pending/job_critic_retry_exec_test.mp3",
        status="COMPLETED",
        overall_score=3.5,
        passed_rubric=False,
        rubric_metrics={
            "Pacing And Pause Structure": {
                "score": 3.0,
                "passed": False,
                "reasoning": "Rushed through bullet points."
            }
        },
        overall_reasoning="Pacing needs improvement.",
        actionable_feedback=["Slow down between key points."]
    )
    repo.save_job(job)

    # 3. Intercept _execute_async_synthesis
    captured_args = {}
    def mock_execute(job_id, text, persona_name, run_judge, title, voice_customization=None, speed=1.0, critique_feedback=None, **kwargs):
        captured_args["job_id"] = job_id
        captured_args["speed"] = speed
        captured_args["critique_feedback"] = critique_feedback

    monkeypatch.setattr("src.ui.app._execute_async_synthesis", mock_execute)

    try:
        # 4. Post retry request with custom critique and speed
        req_payload = {
            "include_critique": True,
            "custom_critique": "CRITICAL: Emphasize numbers slowly and pause at colons.",
            "speed": 0.95
        }
        resp = client.post("/api/jobs/job_critic_retry_exec_test/retry", json=req_payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["job"]["retry_count"] == 1
        assert data["job"]["previous_attempt_score"] == 3.5
        assert data["job"]["remediation_prompt"] == "CRITICAL: Emphasize numbers slowly and pause at colons."
        assert data["job"]["speed"] == 0.95

        # 5. Check mock execution received parameters
        assert captured_args["job_id"] == "job_critic_retry_exec_test"
        assert captured_args["speed"] == 0.95
        assert captured_args["critique_feedback"] == "CRITICAL: Emphasize numbers slowly and pause at colons."

        # 6. Verify in repo
        updated_job = repo.get_job("job_critic_retry_exec_test")
        assert updated_job.retry_count == 1
        assert updated_job.previous_attempt_score == 3.5
        assert updated_job.remediation_prompt == "CRITICAL: Emphasize numbers slowly and pause at colons."
    finally:
        repo.delete_job("job_critic_retry_exec_test")


def test_html_critic_retry_dialog_elements(client):
    """Verify index.html includes the critic-guided retry modal, controls, and detail remediation card."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # Modal Elements
    assert 'id="modalRetryDialog"' in html
    assert 'id="retryModalLoading"' in html
    assert 'id="retryCritiqueText"' in html
    assert 'id="retryIncludeCritique"' in html
    assert 'id="retryPrevScoreBadge"' in html
    assert 'id="retryFlaggedList"' in html
    assert 'id="retrySpeed"' in html
    assert 'id="retrySpeedDisplay"' in html

    # Drawer Elements
    assert 'id="detailRetryBadge"' in html
    assert 'id="detailScoreDeltaBadge"' in html
    assert 'id="detailRemediationCard"' in html
    assert 'id="detailRemediationText"' in html

    # JavaScript Handlers
    assert "openRetryModal" in html
    assert "confirmAndExecuteRetry" in html
    assert "setRetrySpeedPreset" in html


def test_create_podcast_job_api(client, monkeypatch):
    """Verify POST /api/jobs succeeds with podcast personas and director notes."""
    from src.db.repository import get_job_repository
    repo = get_job_repository()

    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    executed_args = {}
    def mock_execute(job_id, text, persona_name, run_judge, title, voice_customization=None, **kwargs):
        executed_args["job_id"] = job_id
        executed_args["persona_name"] = persona_name
        executed_args["voice_customization"] = voice_customization

    monkeypatch.setattr("src.ui.app._execute_async_synthesis", mock_execute)

    payload = {
        "text": "High-Yield Savings vs CDs comparison article.",
        "persona": "Podcast: Co-Hosts (Man & Woman)",
        "title": "Cash Strategy Podcast",
        "voice_customization": "Have Joe focus on emergency fund liquidity while Jane explains CD term penalties."
    }

    resp = client.post("/api/jobs", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    job_id = data["job_id"]

    try:
        assert data["job"]["persona"] == "Podcast: Co-Hosts (Man & Woman)"
        assert data["job"]["voice_customization"] == "Have Joe focus on emergency fund liquidity while Jane explains CD term penalties."
        assert executed_args["persona_name"] == "Podcast: Co-Hosts (Man & Woman)"
        assert executed_args["voice_customization"] == "Have Joe focus on emergency fund liquidity while Jane explains CD term penalties."
    finally:
        repo.delete_job(job_id)


def test_html_podcast_ui_elements(client):
    """Verify HTML templates contain podcast options, directives controls, and script formatting."""
    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    # New Job Modal Options & Optgroups
    assert "2-Person Podcast Co-Hosts (Gemini Multi-Speaker)" in html
    assert 'value="Podcast: Co-Hosts (Man & Woman)"' in html
    assert 'value="Podcast: Co-Hosts (Man & Man)"' in html
    assert 'value="Podcast: Co-Hosts (Woman & Woman)"' in html

    # Auditor View Filter
    assert 'id="personaFilter"' in html
    assert 'Podcast: Co-Hosts (Man & Woman)' in html

    # Director's Notes & Script Controls
    assert 'id="labelVoiceCustomization"' in html
    assert 'id="textVoiceCustomizationLabel"' in html
    assert 'id="btnSampleDirectives"' in html
    assert "handlePersonaChange" in html
    assert "loadSamplePodcastDirectives" in html

    # Podcast Script Studio Elements
    assert 'id="podcastScriptStudioCard"' in html
    assert 'id="inputPodcastScript"' in html
    assert 'id="btnDraftPodcastScript"' in html
    assert 'id="inputEnableWebSearch"' in html
    assert 'id="podcastScriptStats"' in html
    assert 'id="podcastDraftStatus"' in html
    assert "draftPodcastScript" in html
    assert "updatePodcastScriptStats" in html


def test_draft_podcast_script_api_success(client, monkeypatch):
    """Verify /api/podcast/draft-script endpoint drafts a grounded script with stats."""
    from src.ai.generator import PodcastScript, PodcastTurn

    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    fake_script = PodcastScript(
        title="Defense & Debt Breakdown",
        summary="A lively debate on fiscal tradeoffs",
        turns=[
            PodcastTurn(speaker="Joe", text="Welcome everyone! [laughs] Let's dive in.", style="cheerful"),
            PodcastTurn(speaker="Jane", text="[sighs] It's a complicated debate, Joe.", style="measured"),
        ]
    )

    def mock_gen_script(self, text, persona, director_notes=None, target_duration_mins=10, enable_web_search=True, progress_callback=None):
        return fake_script

    monkeypatch.setattr("src.ai.generator.GeminiAudioGenerator.generate_podcast_script", mock_gen_script)

    payload = {
        "text": "A Balancing Act: The Trade-Off Between Debt and Defense spending.",
        "persona": "Podcast: Co-Hosts (Man & Woman)",
        "voice_customization": "Cover debt ceiling risks and defense backlogs",
        "target_duration_mins": 10,
        "enable_web_search": True
    }

    resp = client.post("/api/podcast/draft-script", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()

    assert data["title"] == "Defense & Debt Breakdown"
    assert data["turn_count"] == 2
    assert "**Joe** (cheerful): Welcome everyone! [laughs] Let's dive in." in data["markdown_script"]
    assert "**Jane** (measured): [sighs] It's a complicated debate, Joe." in data["markdown_script"]
    assert data["word_count"] > 0
    assert "estimated_duration_mins" in data
    assert len(data["speakers"]) == 2


def test_draft_podcast_script_api_rejects_non_podcast_persona(client):
    """Verify /api/podcast/draft-script rejects solo narrator personas with 400."""
    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "text": "Article text that does not need a podcast script.",
        "persona": "Retail Banking Guide"
    }

    resp = client.post("/api/podcast/draft-script", json=payload, headers=headers)
    assert resp.status_code == 400
    assert "not a multi-speaker podcast persona" in resp.json()["detail"]


def test_create_job_with_custom_podcast_script(client, monkeypatch):
    """Verify create_job handles pre-drafted custom podcast script and passes it to worker."""
    from src.db.repository import get_job_repository
    repo = get_job_repository()

    login_resp = client.post("/api/auth/login", json={"email": "admin@apexbank.com", "password": "demo1234"})
    assert login_resp.status_code == 200
    token = login_resp.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    executed_args = {}
    def mock_execute(job_id, text, persona_name, run_judge, title, voice_customization=None, podcast_script=None, **kwargs):
        executed_args["job_id"] = job_id
        executed_args["persona_name"] = persona_name
        executed_args["podcast_script"] = podcast_script

    monkeypatch.setattr("src.ui.app._execute_async_synthesis", mock_execute)

    custom_script = "**Joe** (upbeat): Custom script turn 1! [laughs]\n**Jane**: Custom turn 2."
    payload = {
        "text": "Source article for context",
        "persona": "Podcast: Co-Hosts (Man & Woman)",
        "title": "Custom Podcast Show",
        "podcast_script": custom_script
    }

    resp = client.post("/api/jobs", json=payload, headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    job_id = data["job_id"]

    try:
        assert data["job"]["persona"] == "Podcast: Co-Hosts (Man & Woman)"
        assert data["job"]["transcript"] == custom_script
        assert executed_args["podcast_script"] == custom_script
    finally:
        repo.delete_job(job_id)









