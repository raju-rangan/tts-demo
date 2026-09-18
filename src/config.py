"""Central Configuration for Knowledge-to-Speech Platform."""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

def _parse_int(val: str, default: int) -> int:
    try:
        return int(val)
    except (ValueError, TypeError):
        return default

@dataclass(frozen=True)
class Settings:
    project_id: str = os.getenv("GCP_PROJECT_ID", "tts-demo-project")
    location: str = os.getenv("GCP_LOCATION", "us-central1")
    gcs_bucket_base_name: str = os.getenv("GCS_BUCKET_BASE_NAME", "tts-bank-audio")
    gcs_bucket_name: str = os.getenv("GCS_BUCKET_NAME", "")
    gcs_object_expiration_days: int = _parse_int(os.getenv("GCS_OBJECT_EXPIRATION_DAYS", "30"), 30)
    voice_model: str = os.getenv("GEMINI_VOICE_MODEL", "gemini-3.1-flash-tts-preview")
    judge_model: str = os.getenv("GEMINI_JUDGE_MODEL", "gemini-3.8-flash")
    judge_location: str = os.getenv("GEMINI_JUDGE_LOCATION", "global")
    default_persona: str = os.getenv("DEFAULT_VOICE_PERSONA", "Retail Banking Guide")
    sample_rate: int = _parse_int(os.getenv("AUDIO_SAMPLE_RATE", "24000"), 24000)
    bitrate: str = os.getenv("AUDIO_BITRATE", "320k")
    tts_chunk_word_limit: int = _parse_int(os.getenv("TTS_CHUNK_WORD_LIMIT", "400"), 400)

settings = Settings()
