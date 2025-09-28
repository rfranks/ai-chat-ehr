from __future__ import annotations

import sys
from pathlib import Path

from fastapi import FastAPI

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.api_gateway.app import get_app


def test_get_app_returns_fastapi_instance() -> None:
    app = get_app()

    assert isinstance(app, FastAPI)
