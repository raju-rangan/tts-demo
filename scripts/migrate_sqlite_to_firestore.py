#!/usr/bin/env python3
"""
Migration Script: Local SQLite to Google Cloud Firestore (Native Mode)

Migrates all historical speech synthesis jobs, audio GCS references, tokens,
and Gemini 3.8 Flash Multimodal Quality Scorecards from data/tts_jobs.db
into the serverless Cloud Firestore collection.
"""
import os
import sys
import logging
from typing import List

# Ensure repository root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import settings
from src.db.models import JobRecord
from src.db.repository import SQLiteJobRepository, FirestoreJobRepository

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("sqlite_to_firestore_migration")

def run_migration(
    sqlite_path: str = "data/tts_jobs.db",
    project_id: str = None,
    database_name: str = None,
    collection_name: str = None
) -> int:
    project_id = project_id or settings.project_id
    database_name = database_name or settings.firestore_database
    collection_name = collection_name or settings.firestore_collection

    logger.info("=" * 70)
    logger.info("🚀 APEX BANK TTS: SQLITE TO CLOUD FIRESTORE DATA MIGRATION")
    logger.info("=" * 70)
    logger.info(f"SQLite Source DB:    {os.path.abspath(sqlite_path)}")
    logger.info(f"Target GCP Project:  {project_id}")
    logger.info(f"Target Database:     {database_name} (Firestore Native)")
    logger.info(f"Target Collection:   {collection_name}")
    logger.info("-" * 70)

    if not os.path.exists(sqlite_path):
        logger.error(f"Source SQLite database not found at {sqlite_path}")
        return 1

    # 1. Read SQLite records
    sqlite_repo = SQLiteJobRepository(db_path=sqlite_path)
    sqlite_jobs: List[JobRecord] = sqlite_repo.list_jobs(limit=1000)
    logger.info(f"Found {len(sqlite_jobs)} job records in SQLite database.")

    if not sqlite_jobs:
        logger.warning("No jobs to migrate from SQLite.")
        return 0

    # 2. Connect to Cloud Firestore
    try:
        firestore_repo = FirestoreJobRepository(
            project_id=project_id,
            collection_name=collection_name,
            database_name=database_name
        )
        logger.info(f"✓ Connected to Firestore Native database '{database_name}'")
    except Exception as e:
        logger.error(f"Failed to connect to Cloud Firestore: {e}")
        return 1

    # 3. Batch migrate records
    migrated_count = 0
    failed_count = 0

    for idx, job in enumerate(sqlite_jobs, 1):
        try:
            firestore_repo.save_job(job)
            score_str = f"★ {job.overall_score:.2f}" if job.overall_score is not None else "Pending"
            logger.info(
                f"[{idx}/{len(sqlite_jobs)}] Migrated {job.job_id} | {job.persona:<30} | {job.status:<9} | {score_str}"
            )
            migrated_count += 1
        except Exception as err:
            logger.error(f"Failed to migrate job {job.job_id}: {err}")
            failed_count += 1

    # 4. Verify Firestore records
    logger.info("-" * 70)
    verified_jobs = firestore_repo.list_jobs(limit=1000)
    logger.info(f"✓ Cloud Firestore total jobs verified: {len(verified_jobs)}")

    logger.info("=" * 70)
    logger.info(f"MIGRATION COMPLETE: {migrated_count} succeeded, {failed_count} failed.")
    logger.info("=" * 70)
    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    exit_code = run_migration()
    sys.exit(exit_code)
