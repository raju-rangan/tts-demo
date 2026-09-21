#!/usr/bin/env python3
"""
Recalculate Historical Job Costs in Google Cloud Firestore Native.

Applies the latest pricing rates for Gemini 3.1 Flash TTS and Gemini 3.8 Flash
across all existing job documents in the Firestore `tts_jobs` collection:
  - Gemini 3.1 Flash TTS:
      - Text input:  $1.00 / 1M tokens
      - Audio output: $20.00 / 1M tokens
  - Gemini 3.8 Flash (Multimodal Judge):
      - Input:  $0.75 / 1M tokens
      - Output: $3.75 / 1M tokens
"""
import os
import sys
import argparse
import logging
from typing import Dict, Any, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.config import settings
from src.ai.cost_calculator import PRICING, TokenCostCalculator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("firestore_cost_recalculator")

def calculate_costs_for_job(data: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """Computes updated cost breakdown for a Firestore job document."""
    tokens = data.get("token_usage") or {}
    existing_cost = data.get("cost") or {}
    judge_model = data.get("judge_model")

    input_text = int(tokens.get("input_text_tokens", 0) or 0)
    audio_output = int(tokens.get("audio_output_tokens", 0) or 0)
    judge_input = int(tokens.get("judge_input_tokens", 0) or 0)
    judge_output = int(tokens.get("judge_output_tokens", 0) or 0)

    # 1. TTS Cost (gemini-3.1-flash-tts-preview)
    tts_pricing = PRICING.get(settings.voice_model, PRICING["gemini-3.1-flash-tts-preview"])
    tts_cost = (
        (input_text / 1_000_000.0) * tts_pricing.get("text_input_per_1m", 1.00) +
        (audio_output / 1_000_000.0) * tts_pricing.get("audio_output_per_1m", 20.00)
    )

    # 2. Judge Cost (gemini-3.8-flash)
    judge_cost = 0.0
    if judge_model and (judge_input > 0 or judge_output > 0):
        judge_pricing = PRICING.get(judge_model, PRICING["gemini-3.8-flash"])
        judge_cost = (
            (judge_input / 1_000_000.0) * judge_pricing.get("input_per_1m", 0.75) +
            (judge_output / 1_000_000.0) * judge_pricing.get("output_per_1m", 3.750)
        )

    new_cost = {
        "tts_cost_usd": round(tts_cost, 6),
        "judge_cost_usd": round(judge_cost, 6),
        "total_cost_usd": round(tts_cost + judge_cost, 6),
        "currency": "USD"
    }

    # Check if cost has changed
    is_changed = (
        existing_cost.get("tts_cost_usd") != new_cost["tts_cost_usd"] or
        existing_cost.get("judge_cost_usd") != new_cost["judge_cost_usd"] or
        existing_cost.get("total_cost_usd") != new_cost["total_cost_usd"]
    )

    return new_cost, is_changed

def run_recalculation(
    project_id: str = None,
    database_name: str = None,
    collection_name: str = None,
    dry_run: bool = False
) -> int:
    project_id = project_id or settings.project_id
    database_name = database_name or settings.firestore_database
    collection_name = collection_name or settings.firestore_collection

    logger.info("=" * 80)
    logger.info("🔥 GOOGLE CLOUD FIRESTORE: JOB COST RECALCULATION")
    logger.info("=" * 80)
    logger.info(f"Target GCP Project:  {project_id}")
    logger.info(f"Target Database:     {database_name} (Firestore Native)")
    logger.info(f"Target Collection:   {collection_name}")
    logger.info(f"Mode:                {'DRY RUN (No updates will be written)' if dry_run else 'LIVE UPDATE'}")
    logger.info("-" * 80)

    try:
        from google.cloud import firestore
        client = firestore.Client(project=project_id, database=database_name)
    except Exception as err:
        logger.error(f"Failed to connect to Google Cloud Firestore: {err}")
        logger.error("Please verify that Application Default Credentials are valid by running:")
        logger.error("  gcloud auth application-default login")
        return 1

    try:
        docs = list(client.collection(collection_name).stream())
    except Exception as err:
        logger.error(f"Failed to stream documents from collection '{collection_name}': {err}")
        return 1

    logger.info(f"Retrieved {len(docs)} documents from Firestore.")
    if not docs:
        logger.warning(f"No documents found in collection '{collection_name}'.")
        return 0

    header = f"{'Doc ID':<22} | {'Title':<30} | {'Old Total':<10} | {'New Total':<10} | {'Status'}"
    logger.info("-" * 80)
    logger.info(header)
    logger.info("-" * 80)

    updated_count = 0
    unchanged_count = 0
    failed_count = 0

    for doc in docs:
        data = doc.to_dict() or {}
        doc_id = doc.id
        title = (data.get("article_title") or "Untitled")[:28]
        old_cost = data.get("cost") or {}
        old_total = old_cost.get("total_cost_usd", 0.0)

        new_cost, is_changed = calculate_costs_for_job(data)
        new_total = new_cost["total_cost_usd"]

        if is_changed:
            if not dry_run:
                try:
                    doc.reference.update({"cost": new_cost})
                    status_str = "UPDATED"
                    updated_count += 1
                except Exception as update_err:
                    status_str = f"FAILED: {update_err}"
                    failed_count += 1
            else:
                status_str = "WOULD UPDATE"
                updated_count += 1
        else:
            status_str = "UNCHANGED"
            unchanged_count += 1

        logger.info(f"{doc_id:<22} | {title:<30} | ${old_total:<9.6f} | ${new_total:<9.6f} | {status_str}")

    logger.info("=" * 80)
    logger.info(f"RECALCULATION COMPLETE: {updated_count} updated, {unchanged_count} unchanged, {failed_count} failed.")
    logger.info("=" * 80)
    return 0 if failed_count == 0 else 1

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recalculate historical job costs in Cloud Firestore.")
    parser.add_argument("--dry-run", action="store_true", help="Calculate and preview costs without modifying Firestore.")
    parser.add_argument("--project", default=None, help="GCP project ID.")
    parser.add_argument("--database", default=None, help="Firestore database name.")
    parser.add_argument("--collection", default=None, help="Firestore collection name.")
    args = parser.parse_args()

    sys.exit(run_migration := run_recalculation(
        project_id=args.project,
        database_name=args.database,
        collection_name=args.collection,
        dry_run=args.dry_run
    ))
