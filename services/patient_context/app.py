"""FastAPI application exposing patient context capabilities."""

from __future__ import annotations

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, status

from repositories.emr import EMRRepository
from services.patient_context.mappers import map_patient_context, map_patient_record
from shared.models import EHRPatientContext, PatientRecord
from shared.observability.logger import configure_logging
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)
from shared.http.errors import register_exception_handlers

SERVICE_NAME = "patient_context"

configure_logging(service_name=SERVICE_NAME)

app = FastAPI(title="Patient Context Service")
router = APIRouter(prefix="/patients", tags=["patients"])
_repository = EMRRepository()

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)


def get_repository() -> EMRRepository:
    """Return the shared :class:`EMRRepository` instance."""

    return _repository


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return a simple health payload for orchestration checks."""

    return {"status": "ok", "service": SERVICE_NAME}


@router.get("/{patient_id}", response_model=PatientRecord, status_code=status.HTTP_200_OK)
async def read_patient_record(
    patient_id: str, repo: EMRRepository = Depends(get_repository)
) -> PatientRecord:
    """Return the normalized patient record for ``patient_id``."""

    raw_record = await repo.fetch_patient_record(patient_id)
    if raw_record is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' was not found.",
        )
    try:
        return map_patient_record(raw_record)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to normalize patient record: {exc}",
        ) from exc


@router.get(
    "/context",
    response_model=EHRPatientContext,
    status_code=status.HTTP_200_OK,
)
async def read_patient_context(
    patient_id: str = Query(..., description="Unique identifier for the patient"),
    repo: EMRRepository = Depends(get_repository),
) -> EHRPatientContext:
    """Return the chat-oriented patient context for ``patient_id``."""

    raw_context = await repo.fetch_patient_context(patient_id)
    if raw_context is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient '{patient_id}' was not found.",
        )
    try:
        return map_patient_context(raw_context)
    except ValueError as exc:  # pragma: no cover - defensive branch
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unable to normalize patient context: {exc}",
        ) from exc


app.include_router(router)


__all__ = ["app", "get_repository", "health"]
