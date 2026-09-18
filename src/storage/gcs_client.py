"""Google Cloud Storage Client for Audio Assets with Audience Prefix Routing and Lifecycle Management."""
import os
import re
import random
import string
import datetime
import logging
from typing import Optional, Tuple, List, Dict, Any
from google.cloud import storage
from src.config import settings
from src.ai.personas import PERSONAS

logger = logging.getLogger(__name__)

class GCSStorageClient:
    """Manages audio file storage, bucket lifecycle, and audience prefix routing in Google Cloud Storage."""

    def __init__(self, bucket_name: Optional[str] = None, project_id: Optional[str] = None):
        self.project_id = project_id or settings.project_id
        self.bucket_name = bucket_name or settings.gcs_bucket_name
        self._client: Optional[storage.Client] = None

    @property
    def client(self) -> storage.Client:
        """Lazy initialized GCS Client."""
        if self._client is None:
            self._client = storage.Client(project=self.project_id)
        return self._client

    @staticmethod
    def generate_bucket_name(base_name: Optional[str] = None) -> str:
        """Generates a bucket name formatted as {base_name}-{random_5_chars}."""
        base = (base_name or settings.gcs_bucket_base_name or "tts-bank-audio").lower().strip()
        # Clean base name for GCS compliance: lowercase letters, numbers, dashes
        base = re.sub(r"[^a-z0-9-]", "-", base).strip("-")
        rand_suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=5))
        return f"{base}-{rand_suffix}"

    @staticmethod
    def get_prefix_for_persona(persona_name: Optional[str] = None, audience: Optional[str] = None) -> str:
        """
        Determines the GCS object prefix key based on persona audience for IAM condition access control.
        - External Customers -> external/audio
        - Internal Employees -> internal/audio
        - Both / Shared      -> shared/audio
        """
        resolved_audience = audience
        if not resolved_audience and persona_name:
            persona = PERSONAS.get(persona_name)
            if persona:
                resolved_audience = persona.audience

        if resolved_audience == "Internal Employees":
            return "internal/audio"
        elif resolved_audience == "Both":
            return "shared/audio"
        else:
            return "external/audio"

    @staticmethod
    def get_iam_condition_examples(bucket_name: str) -> Dict[str, str]:
        """Returns sample Cloud IAM CEL conditions for prefix-based access control."""
        return {
            "external_public": f'resource.name.startsWith("projects/_/buckets/{bucket_name}/objects/external/")',
            "internal_restricted": f'resource.name.startsWith("projects/_/buckets/{bucket_name}/objects/internal/")',
            "shared_alerts": f'resource.name.startsWith("projects/_/buckets/{bucket_name}/objects/shared/")',
        }

    def apply_lifecycle_rule(self, bucket: storage.Bucket, expiration_days: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Applies or clears object lifecycle expiration rules.
        If expiration_days > 0, enforces object deletion after expiration_days.
        If expiration_days == 0, removes any Delete lifecycle rules (indefinite retention).
        """
        days = settings.gcs_object_expiration_days if expiration_days is None else expiration_days

        # Remove existing Delete rules
        existing_rules = list(bucket.lifecycle_rules or [])
        filtered_rules = [
            rule for rule in existing_rules
            if not (isinstance(rule, dict) and rule.get("action", {}).get("type") == "Delete")
        ]

        if days > 0:
            filtered_rules.append({"action": {"type": "Delete"}, "condition": {"age": days}})
            bucket.lifecycle_rules = filtered_rules
            bucket.patch()
            logger.info(f"Enforced GCS lifecycle expiration rule: delete after {days} days on bucket '{bucket.name}'.")
        else:
            if len(filtered_rules) != len(existing_rules):
                bucket.lifecycle_rules = filtered_rules
                bucket.patch()
            logger.info(f"GCS lifecycle expiration set to 0. No delete rule active on bucket '{bucket.name}'.")

        return list(bucket.lifecycle_rules or [])

    @staticmethod
    def save_bucket_name_to_env(bucket_name: str, env_path: str = ".env") -> bool:
        """Persists the resolved bucket name to the .env file so subsequent runs reuse it."""
        try:
            if not os.path.exists(env_path):
                example_path = f"{env_path}.example"
                if os.path.exists(example_path):
                    with open(example_path, "r", encoding="utf-8") as f:
                        content = f.read()
                else:
                    content = "GCS_BUCKET_NAME=\n"
                with open(env_path, "w", encoding="utf-8") as f:
                    f.write(content)

            with open(env_path, "r", encoding="utf-8") as f:
                lines = f.readlines()

            bucket_set = False
            new_lines = []
            for line in lines:
                if line.startswith("GCS_BUCKET_NAME="):
                    new_lines.append(f"GCS_BUCKET_NAME={bucket_name}\n")
                    bucket_set = True
                else:
                    new_lines.append(line)

            if not bucket_set:
                new_lines.append(f"GCS_BUCKET_NAME={bucket_name}\n")

            with open(env_path, "w", encoding="utf-8") as f:
                f.writelines(new_lines)

            logger.info(f"Persisted GCS_BUCKET_NAME={bucket_name} to {env_path}")
            return True
        except Exception as e:
            logger.warning(f"Could not persist bucket name to {env_path}: {e}")
            return False

    def ensure_bucket_exists(
        self,
        bucket_name: Optional[str] = None,
        location: Optional[str] = None
    ) -> storage.Bucket:
        """
        Ensures target bucket exists. If not, creates it with {base_name}-{random_5_chars},
        enables Uniform Bucket-Level Access, applies the lifecycle rule, and saves to .env.
        """
        target_name = bucket_name or self.bucket_name
        loc = location or settings.location

        if not target_name:
            target_name = self.generate_bucket_name(settings.gcs_bucket_base_name)
            logger.info(f"Generated new bucket name: {target_name}")

        try:
            bucket = self.client.lookup_bucket(target_name)
        except Exception as e:
            logger.warning(f"Lookup for bucket '{target_name}' encountered: {e}. Attempting creation.")
            bucket = None

        if bucket is None:
            logger.info(f"Bucket '{target_name}' not found. Creating in project '{self.project_id}' at '{loc}'...")
            bucket = self.client.create_bucket(target_name, project=self.project_id, location=loc)
            
            # Enable Uniform Bucket-Level Access for prefix-based IAM Conditions
            bucket.iam_configuration.uniform_bucket_level_access_enabled = True
            bucket.patch()
            
            # Apply object lifecycle rule (30 days vs 0)
            self.apply_lifecycle_rule(bucket, settings.gcs_object_expiration_days)
            
            # Save to .env and local state
            self.save_bucket_name_to_env(target_name)
            self.bucket_name = target_name
            logger.info(f"✓ GCS Bucket '{target_name}' created and configured successfully.")
        else:
            # Sync lifecycle rule if bucket already exists
            self.apply_lifecycle_rule(bucket, settings.gcs_object_expiration_days)
            self.bucket_name = target_name

        return bucket

    def upload_audio_bytes(
        self,
        audio_bytes: bytes,
        job_id: str,
        persona_name: Optional[str] = None,
        audience: Optional[str] = None,
        content_type: str = "audio/mpeg",
        metadata: Optional[dict] = None
    ) -> Tuple[str, str]:
        """
        Uploads audio bytes to GCS under the audience-specific prefix and returns (gcs_uri, signed_url).
        Blob path: {prefix}/{job_id}.mp3
        """
        prefix = self.get_prefix_for_persona(persona_name=persona_name, audience=audience)
        blob_path = f"{prefix}/{job_id}.mp3"

        if not self.bucket_name:
            self.ensure_bucket_exists()

        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(blob_path)

        # Build comprehensive metadata for governance & audit
        resolved_persona = persona_name or settings.default_persona
        persona_obj = PERSONAS.get(resolved_persona)
        meta = {
            "job_id": job_id,
            "persona": resolved_persona,
            "audience": audience or (persona_obj.audience if persona_obj else "External Customers"),
            "prefix": prefix,
            "expiration_days": str(settings.gcs_object_expiration_days),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat()
        }
        if metadata:
            meta.update(metadata)

        blob.metadata = meta
        blob.upload_from_string(audio_bytes, content_type=content_type)
        gcs_uri = f"gs://{self.bucket_name}/{blob_path}"

        # Generate a 60-minute signed URL
        try:
            signed_url = blob.generate_signed_url(
                version="v4",
                expiration=datetime.timedelta(minutes=60),
                method="GET"
            )
        except Exception as e:
            logger.warning(f"Could not generate signed URL (requires service account credentials): {e}")
            signed_url = f"https://storage.googleapis.com/{self.bucket_name}/{blob_path}"

        return gcs_uri, signed_url

    def upload_file(
        self,
        local_file_path: str,
        job_id: str,
        persona_name: Optional[str] = None,
        audience: Optional[str] = None,
        content_type: str = "audio/mpeg"
    ) -> Tuple[str, str]:
        """Uploads a local audio file to GCS with audience prefix routing."""
        with open(local_file_path, "rb") as f:
            data = f.read()
        return self.upload_audio_bytes(
            audio_bytes=data,
            job_id=job_id,
            persona_name=persona_name,
            audience=audience,
            content_type=content_type
        )

    def object_exists(self, blob_path: str) -> bool:
        """Checks if a blob exists in the bucket."""
        bucket = self.client.bucket(self.bucket_name)
        blob = bucket.blob(blob_path)
        return blob.exists()
