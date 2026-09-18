"""Centralized logging configuration for Knowledge-to-Speech Platform.

Streams logs simultaneously to:
1. Google Cloud Logging (projects/{project_id}/logs/tts-studio)
2. Local persistent rotating file (logs/app.log)
3. Standard Output (Console)
"""
import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from typing import Optional

from src.config import settings

LOG_DIR = 'logs'
DEFAULT_LOG_FILE = os.path.join(LOG_DIR, 'app.log')
LOG_FORMAT = '%(asctime)s [%(levelname)s] [%(name)s]: %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

_logging_configured = False


def setup_logging(
    log_file: str = DEFAULT_LOG_FILE,
    level: int = logging.INFO,
    gcp_project_id: Optional[str] = None
) -> None:
    """Configures root and application loggers with GCP Cloud Logging, file rotation, and console."""
    global _logging_configured
    if _logging_configured:
        return

    os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
    formatter = logging.Formatter(fmt=LOG_FORMAT, datefmt=DATE_FORMAT)

    handlers = []

    # 1. Console Stream Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    handlers.append(console_handler)

    # 2. Local Rotating File Handler (10MB, 5 archives)
    try:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    except Exception as e:
        print(f'Warning: Could not initialize file logging handler for {log_file}: {e}', file=sys.stderr)

    # 3. Google Cloud Logging Handler
    if not os.getenv("PYTEST_CURRENT_TEST"):
        target_project = gcp_project_id or settings.project_id
        try:
            import google.cloud.logging
            client = google.cloud.logging.Client(project=target_project)
            gcp_handler = client.get_default_handler(name='tts-studio')
            gcp_handler.setLevel(level)
            handlers.append(gcp_handler)
            print(f"✓ Google Cloud Logging initialized for project '{target_project}' (logName: 'tts-studio')")
        except Exception as e:
            print(f'Notice: Google Cloud Logging not attached ({e}). Defaulting to file and console logging.', file=sys.stderr)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    root_logger.handlers = []
    for h in handlers:
        root_logger.addHandler(h)

    # Re-route uvicorn loggers
    for uvicorn_logger_name in ('uvicorn', 'uvicorn.error', 'uvicorn.access'):
        u_logger = logging.getLogger(uvicorn_logger_name)
        u_logger.handlers = []
        for h in handlers:
            u_logger.addHandler(h)
        u_logger.propagate = False

    _logging_configured = True
    logging.getLogger('src.utils.logger').info('Logging system initialized: Google Cloud Logging + Rotating File + Console active.')


def get_recent_logs(lines: int = 100, log_file: str = DEFAULT_LOG_FILE) -> str:
    """Reads the last N lines from the local log file for quick inspection or diagnostic API."""
    if not os.path.exists(log_file):
        return f'Log file "{log_file}" does not exist yet.'
    try:
        with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
            all_lines = f.readlines()
            recent = all_lines[-lines:] if len(all_lines) > lines else all_lines
            return ''.join(recent)
    except Exception as e:
        return f'Error reading log file "{log_file}": {e}'
