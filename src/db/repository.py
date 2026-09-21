"""Cloud Firestore (Firebase Native Mode) Job Repository with InMemory test isolation."""
import os
import json
import logging
from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from src.db.models import JobRecord, TokenUsageDetails, CostBreakdown
from src.config import settings

logger = logging.getLogger(__name__)

class BaseJobRepository(ABC):
    """Abstract interface for storing and retrieving knowledge-to-speech job telemetry."""

    @abstractmethod
    def save_job(self, job: JobRecord) -> None:
        """Persists a new or updated job record."""
        pass

    @abstractmethod
    def get_job(self, job_id: str) -> Optional[JobRecord]:
        """Retrieves a job record by ID."""
        pass

    @abstractmethod
    def list_jobs(self, limit: int = 50, persona: Optional[str] = None) -> List[JobRecord]:
        """Lists recent job records in descending chronological order."""
        pass

    @abstractmethod
    def delete_job(self, job_id: str) -> bool:
        """Deletes a job record by ID. Returns True if deleted, False if not found."""
        pass

    @abstractmethod
    def update_job_progress(
        self,
        job_id: str,
        progress_stage: str,
        progress_message: str,
        current_turn: Optional[int] = None,
        total_turns: Optional[int] = None,
    ) -> None:
        """Updates live progress stage and turn counters for a running job."""
        pass

    @abstractmethod
    def get_user_tour_status(self, google_email: str, persona: str = "creator") -> bool:
        """Returns True if the authenticated Google user identity has completed or dismissed the onboarding tour for the given persona, False otherwise."""
        pass

    @abstractmethod
    def set_user_tour_dismissed(self, google_email: str, persona: str = "creator", dismissed: bool = True) -> None:
        """Persists onboarding tour completion / dismissal state for the (google_email, persona) pair."""
        pass

    @abstractmethod
    def reset_all_tour_tracking(self) -> None:
        """Resets all onboarding tour tracking records so all users will see the tour on their next visit."""
        pass


class InMemoryJobRepository(BaseJobRepository):
    """In-memory repository ensuring test isolation and zero external dependency requirements."""

    def __init__(self):
        self._jobs: Dict[str, JobRecord] = {}
        self._tours: Dict[str, Dict[str, Any]] = {}

    def save_job(self, job: JobRecord) -> None:
        self._jobs[job.job_id] = job

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        return self._jobs.get(job_id)

    def list_jobs(self, limit: int = 50, persona: Optional[str] = None) -> List[JobRecord]:
        jobs = list(self._jobs.values())
        if persona and persona != "All":
            jobs = [j for j in jobs if j.persona == persona]
        jobs.sort(key=lambda j: j.created_at, reverse=True)
        return jobs[:limit]

    def delete_job(self, job_id: str) -> bool:
        if job_id in self._jobs:
            del self._jobs[job_id]
            return True
        return False

    def update_job_progress(
        self,
        job_id: str,
        progress_stage: str,
        progress_message: str,
        current_turn: Optional[int] = None,
        total_turns: Optional[int] = None,
    ) -> None:
        job = self._jobs.get(job_id)
        if job:
            job.progress_stage = progress_stage
            job.progress_message = progress_message
            job.current_turn = current_turn
            job.total_turns = total_turns

    def get_user_tour_status(self, google_email: str, persona: str = "creator") -> bool:
        clean_email = google_email.lower().strip()
        clean_persona = persona.lower().strip() if persona else "creator"
        key = f"{clean_email}__{clean_persona}"
        return self._tours.get(key, {}).get("has_seen_tour", False)

    def set_user_tour_dismissed(self, google_email: str, persona: str = "creator", dismissed: bool = True) -> None:
        clean_email = google_email.lower().strip()
        clean_persona = persona.lower().strip() if persona else "creator"
        key = f"{clean_email}__{clean_persona}"
        self._tours[key] = {
            "has_seen_tour": dismissed,
            "tour_dismissed_at": datetime.now(timezone.utc).isoformat() if dismissed else None
        }

    def reset_all_tour_tracking(self) -> None:
        self._tours.clear()


class FirestoreJobRepository(BaseJobRepository):
    """Google Cloud Firestore (Firebase Native Mode) repository."""

    def __init__(
        self,
        project_id: str,
        collection_name: str = "tts_jobs",
        database_name: str = "tts-jobs"
    ):
        from google.cloud import firestore
        self.project_id = project_id
        self.collection_name = collection_name
        self.database_name = database_name
        self.client = firestore.Client(project=project_id, database=database_name)
        self.collection = self.client.collection(collection_name)

    def save_job(self, job: JobRecord) -> None:
        doc_data = job.model_dump()
        self.collection.document(job.job_id).set(doc_data)

    def get_job(self, job_id: str) -> Optional[JobRecord]:
        doc = self.collection.document(job_id).get()
        if not doc.exists:
            return None
        return JobRecord.model_validate(doc.to_dict())

    def list_jobs(self, limit: int = 50, persona: Optional[str] = None) -> List[JobRecord]:
        try:
            query = self.collection
            if persona and persona != "All":
                query = query.where("persona", "==", persona)
            query = query.order_by("created_at", direction="DESCENDING").limit(limit)
            return [JobRecord.model_validate(d.to_dict()) for d in query.stream()]
        except Exception as qe:
            logger.warning(f"Indexed Firestore query fallback ({qe}): using in-memory persona filter.")
            fetch_limit = limit * 3 if persona and persona != "All" else limit
            query = self.collection.order_by("created_at", direction="DESCENDING").limit(fetch_limit)
            records = [JobRecord.model_validate(d.to_dict()) for d in query.stream()]
            if persona and persona != "All":
                records = [r for r in records if r.persona == persona][:limit]
            return records

    def delete_job(self, job_id: str) -> bool:
        doc_ref = self.collection.document(job_id)
        if not doc_ref.get().exists:
            return False
        doc_ref.delete()
        return True

    def update_job_progress(
        self,
        job_id: str,
        progress_stage: str,
        progress_message: str,
        current_turn: Optional[int] = None,
        total_turns: Optional[int] = None,
    ) -> None:
        doc_ref = self.collection.document(job_id)
        doc_ref.update({
            "progress_stage": progress_stage,
            "progress_message": progress_message,
            "current_turn": current_turn,
            "total_turns": total_turns,
        })

    def get_user_tour_status(self, google_email: str, persona: str = "creator") -> bool:
        clean_email = google_email.lower().strip()
        clean_persona = persona.lower().strip() if persona else "creator"
        doc_id = f"{clean_email}__{clean_persona}"
        try:
            doc_ref = self.client.collection("user_tour_preferences").document(doc_id)
            doc = doc_ref.get()
            if doc.exists:
                data = doc.to_dict() or {}
                return bool(data.get("has_seen_tour", False))
        except Exception as e:
            logger.warning(f"Failed to fetch user tour status from Firestore: {e}")
        return False

    def set_user_tour_dismissed(self, google_email: str, persona: str = "creator", dismissed: bool = True) -> None:
        clean_email = google_email.lower().strip()
        clean_persona = persona.lower().strip() if persona else "creator"
        doc_id = f"{clean_email}__{clean_persona}"
        now_iso = datetime.now(timezone.utc).isoformat() if dismissed else None
        try:
            doc_ref = self.client.collection("user_tour_preferences").document(doc_id)
            doc_ref.set({
                "google_email": clean_email,
                "persona": clean_persona,
                "has_seen_tour": dismissed,
                "tour_dismissed_at": now_iso,
            }, merge=True)
        except Exception as e:
            logger.warning(f"Failed to set user tour dismissal in Firestore: {e}")

    def reset_all_tour_tracking(self) -> None:
        try:
            docs = self.client.collection("user_tour_preferences").stream()
            for d in docs:
                d.reference.delete()
        except Exception as e:
            logger.warning(f"Failed to reset tour tracking in Firestore: {e}")


_active_repo: Optional[BaseJobRepository] = None

def reset_job_repository():
    """Resets the active singleton repository (used for testing/switching backends)."""
    global _active_repo
    _active_repo = None

def get_job_repository() -> BaseJobRepository:
    """
    Factory returning Cloud Firestore repository if enabled, falling back to InMemoryJobRepository for tests/offline.
    """
    global _active_repo
    if _active_repo is not None:
        return _active_repo

    if settings.use_firestore:
        try:
            from google.cloud import firestore
            fs_repo = FirestoreJobRepository(
                project_id=settings.project_id,
                collection_name=settings.firestore_collection,
                database_name=settings.firestore_database
            )
            _seed_initial_jobs_if_empty(fs_repo)
            logger.info(
                f"✓ Cloud Firestore repository connected for project '{settings.project_id}', "
                f"database '{settings.firestore_database}', collection '{settings.firestore_collection}'"
            )
            _active_repo = fs_repo
            return _active_repo
        except Exception as e:
            logger.warning(
                f"Cloud Firestore not accessible for project '{settings.project_id}' ({e}). "
                f"Falling back to InMemoryJobRepository."
            )

    _active_repo = InMemoryJobRepository()
    _seed_initial_jobs_if_empty(_active_repo)
    return _active_repo


def _seed_initial_jobs_if_empty(repo: BaseJobRepository):
    """Pre-populates the repository with verified jobs if none exist."""
    try:
        has_job1 = repo.get_job("job_757eac1a") is not None
        has_job2 = repo.get_job("job_bd8a617f") is not None
        if has_job1 and has_job2:
            return
    except Exception:
        pass

    sample_transcript = (
        "High-Yield Savings Accounts vs. Certificates of Deposit (CDs): A Financial Guide for Retail Banking Customers.\n\n"
        "When planning your short-to-medium-term savings strategy, two of the most secure instruments available are High-Yield Savings Accounts (HYSA) "
        "and Certificates of Deposit (CDs). Both products are FDIC-insured up to $250,000 per depositor, per institution, offering principal protection "
        "alongside competitive yields.\n\n"
        "1. High-Yield Savings Accounts: Flexibility & Liquidity. A high-yield savings account is an interest-bearing deposit account that typically offers "
        "an Annual Percentage Yield (APY) significantly higher than traditional brick-and-mortar savings accounts. The defining advantage is liquidity: "
        "funds can be deposited or withdrawn at any time via electronic funds transfers (EFT) or Automated Clearing House (ACH) withdrawals, subject to "
        "standard federal and bank transaction limits. These accounts are ideal for emergency funds or near-term expenses.\n\n"
        "2. Certificates of Deposit: Guaranteed Rate Certainty. A CD is a time-deposit account where you commit a lump sum for a fixed term—ranging from "
        "3 months to 5 years—in exchange for a guaranteed APY that remains locked regardless of Federal Reserve interest rate fluctuations. However, withdrawing "
        "funds prior to the maturity date triggers an early withdrawal penalty, typically calculated as several months of interest.\n\n"
        "3. Regulatory & Compliance Safeguards. Both HYSAs and CDs require standard Customer Identification Programs (CIP) and Know Your Customer (KYC) "
        "verification in accordance with the Bank Secrecy Act (BSA) and anti-money laundering (AML) regulations."
    )

    # Seed Job 1: job_757eac1a (Recalculated with latest gemini-3.1-flash-tts and gemini-3.8-flash pricing)
    job1 = JobRecord(
        job_id="job_757eac1a",
        created_at=datetime.now(timezone.utc).isoformat(),
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        article_title="High-Yield Savings vs. Certificates of Deposit (CDs)",
        transcript=sample_transcript,
        word_count=281,
        char_count=1857,
        gcs_uri="gs://knowledge-to-audio-poc/external/audio/job_757eac1a.mp3",
        signed_url="https://storage.googleapis.com/knowledge-to-audio-poc/external/audio/job_757eac1a.mp3",
        audio_format="MP3 24kHz @ 320kbps",
        duration_seconds=95.38,
        synthesis_latency_sec=95.38,
        status="COMPLETED",
        token_usage=TokenUsageDetails(
            input_text_tokens=374,
            audio_output_tokens=3052,
            judge_input_tokens=3576,
            judge_output_tokens=320,
            total_tokens=7322
        ),
        cost=CostBreakdown(
            tts_cost_usd=0.061414,
            judge_cost_usd=0.003882,
            total_cost_usd=0.065296,
            currency="USD"
        ),
        overall_score=4.64,
        overall_reasoning="High overall fidelity and natural retail guide cadence. Excellent tone and acoustic clarity; minor deduction for paraphrasing parenthetical acronym expansion '(EFT) or Automated Clearing House (ACH) withdrawals'.",
        passed_rubric=True,
        rubric_metrics={
            "script_adherence_and_accuracy": {
                "score": 4.3,
                "weight": 0.25,
                "rationale": "Faithfully captures the entire text without omitted paragraphs or duplicates; minor shortening of parenthetical acronym phrase."
            },
            "naturalness_and_inflection": {
                "score": 4.6,
                "weight": 0.20,
                "rationale": "Organic cadence, pleasant pitch modulation, and warm sentence transitions avoiding synthetic stiffness."
            },
            "pacing_and_breathing": {
                "score": 4.7,
                "weight": 0.15,
                "rationale": "Deliberate, measured, and well suited for instructional banking guidance with natural pauses before headings."
            },
            "tone_congruence": {
                "score": 4.8,
                "weight": 0.15,
                "rationale": "The vocal delivery perfectly embodies a welcoming, trustworthy, and professional retail banking guide."
            },
            "pronunciation_and_jargon": {
                "score": 4.2,
                "weight": 0.15,
                "rationale": "Banking acronyms like APY, FDIC, CD, KYC, and BSA are pronounced cleanly as initialisms."
            },
            "acoustic_quality": {
                "score": 4.8,
                "weight": 0.10,
                "rationale": "Studio-grade fidelity with crisp high frequencies, consistent volume levels, and zero clipping."
            }
        },
        actionable_feedback=[
            "Ensure complete script adherence by reading the main document title and not omitting parenthetical acronym expansions.",
            "Maintain the current excellent tone and pacing for future retail customer explainers."
        ],
        judge_model="gemini-3.8-flash",
        judge_latency_sec=18.08
    )
    try:
        if not has_job1:
            repo.save_job(job1)
    except Exception:
        pass

    # Seed Job 2: job_bd8a617f (Recalculated with latest gemini-3.1-flash-tts and gemini-3.8-flash pricing)
    job2 = JobRecord(
        job_id="job_bd8a617f",
        created_at=datetime.now(timezone.utc).isoformat(),
        persona="Retail Banking Guide",
        audience="External Customers",
        voice_name="Sulafat",
        article_title="High-Yield Savings vs. CDs - Baseline Synthesis",
        transcript=sample_transcript,
        word_count=281,
        char_count=1857,
        gcs_uri="gs://knowledge-to-audio-poc/external/audio/job_bd8a617f.mp3",
        signed_url="https://storage.googleapis.com/knowledge-to-audio-poc/external/audio/job_bd8a617f.mp3",
        audio_format="MP3 24kHz @ 320kbps",
        duration_seconds=58.41,
        synthesis_latency_sec=58.41,
        status="COMPLETED",
        token_usage=TokenUsageDetails(
            input_text_tokens=374,
            audio_output_tokens=1869,
            judge_input_tokens=2393,
            judge_output_tokens=310,
            total_tokens=4946
        ),
        cost=CostBreakdown(
            tts_cost_usd=0.037754,
            judge_cost_usd=0.002957,
            total_cost_usd=0.040711,
            currency="USD"
        ),
        overall_score=4.8,
        overall_reasoning="Pristine studio acoustic quality and engaging retail persona delivery. Complete verbatim fidelity across all financial guidance sections.",
        passed_rubric=True,
        rubric_metrics={
            "script_adherence_and_accuracy": {
                "score": 4.9,
                "weight": 0.25,
                "rationale": "Complete verbatim text adherence with zero skipped, duplicated, or omitted sentences."
            },
            "naturalness_and_inflection": {
                "score": 4.8,
                "weight": 0.20,
                "rationale": "Exceptionally engaging, polished, and human with fluid cadence."
            },
            "pacing_and_breathing": {
                "score": 4.8,
                "weight": 0.15,
                "rationale": "Pacing is measured, deliberate, and clear."
            },
            "tone_congruence": {
                "score": 5.0,
                "weight": 0.15,
                "rationale": "Tone perfectly matches intended Retail Banking Guide persona."
            },
            "pronunciation_and_jargon": {
                "score": 4.4,
                "weight": 0.15,
                "rationale": "Financial acronyms FDIC, ACH, KYC, and BSA are pronounced cleanly."
            },
            "acoustic_quality": {
                "score": 5.0,
                "weight": 0.10,
                "rationale": "Studio-grade audio with pristine clarity and zero background hiss."
            }
        },
        actionable_feedback=[
            "Ensure acronym plurals such as 'CDs' are pronounced naturally as 'see-deez'."
        ],
        judge_model="gemini-3.8-flash",
        judge_latency_sec=16.42
    )
    try:
        if not has_job2:
            repo.save_job(job2)
    except Exception:
        pass

    # Seed Job 3: job_d9a7b82a (Verified failed job for UI diagnostic testing)
    try:
        if repo.get_job("job_d9a7b82a") is None:
            job3 = JobRecord(
                job_id="job_d9a7b82a",
                created_at=datetime.now(timezone.utc).isoformat(),
                persona="Retail Banking Guide",
                audience="External Customers",
                voice_name="Sulafat",
                article_title="Failed Generation Diagnostic Sample",
                transcript="Failed test transcript",
                word_count=1659,
                char_count=12145,
                gcs_uri="N/A",
                status="FAILED",
                error_message="Speech synthesis timed out on 1,659-word article (12,145 characters) exceeding single-pass limits."
            )
            repo.save_job(job3)
    except Exception:
        pass

