import os
import pytest

# Force isolated in-memory repository backend for all tests
os.environ["USE_FIRESTORE"] = "false"

from src.config import Settings
import src.config
src.config.settings = Settings(use_firestore=False)

from src.db.repository import reset_job_repository
reset_job_repository()

@pytest.fixture(autouse=True)
def force_in_memory_repo():
    """Ensure every test runs isolated against in-memory backend without external calls."""
    os.environ["USE_FIRESTORE"] = "false"
    src.config.settings = Settings(use_firestore=False)
    reset_job_repository()
    yield
    reset_job_repository()
