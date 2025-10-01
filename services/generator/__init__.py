"""Generator service package exposing the FastAPI application factory."""

from pathlib import Path

from dotenv import load_dotenv

from .app import app, get_app

__all__ = ["__version__", "app", "get_app"]

__version__ = "0.1.0"

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
