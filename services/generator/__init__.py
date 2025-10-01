"""Generator service package exposing the FastAPI application factory."""

from pathlib import Path

from dotenv import load_dotenv

from .observability import cli_request_context, logger, scrub_for_logging
from .app import app, get_app

__all__ = [
    "__version__",
    "app",
    "cli_request_context",
    "get_app",
    "logger",
    "scrub_for_logging",
]

__version__ = "0.1.0"

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
