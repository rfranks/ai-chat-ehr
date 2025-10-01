"""Anonymizer service package."""

from pathlib import Path

from dotenv import load_dotenv

from .presidio_engine import (
    AnonymizationAction,
    EntityAnonymizationRule,
    PresidioAnonymizerEngine,
    PresidioEngineConfig,
    SAFE_HARBOR_ENTITIES,
)

__all__ = [
    "__version__",
    "AnonymizationAction",
    "EntityAnonymizationRule",
    "PresidioAnonymizerEngine",
    "PresidioEngineConfig",
    "SAFE_HARBOR_ENTITIES",
]

__version__ = "0.1.0"

load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=False)
