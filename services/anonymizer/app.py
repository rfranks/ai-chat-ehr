"""FastAPI application providing anonymization capabilities."""

from __future__ import annotations

from typing import Any, Annotated

from fastapi import APIRouter, FastAPI, HTTPException, Path, status

from shared.http.errors import register_exception_handlers
from shared.observability.logger import configure_logging, get_logger
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

from services.anonymizer.logging_utils import scrub_for_logging
from services.anonymizer.reporting import summarize_transformations
from services.anonymizer.service import (
    DuplicatePatientError,
    PatientNotFoundError,
    PatientProcessingError,
    ServiceConfigurationError,
    process_patient,
)

SERVICE_NAME = "anonymizer"

configure_logging(service_name=SERVICE_NAME)

logger = get_logger(__name__)

app = FastAPI(title="Anonymizer Service")
router = APIRouter(prefix="/anonymizer", tags=["anonymizer"])

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    """Return service health status metadata."""

    return {"status": "ok", "service": SERVICE_NAME}


CollectionParam = Annotated[
    str,
    Path(
        ...,
        min_length=1,
        max_length=128,
        regex=r"^[A-Za-z0-9_.-]+$",
        description="Name of the Firestore collection containing the patient document.",
    ),
]

DocumentParam = Annotated[
    str,
    Path(
        ...,
        min_length=1,
        max_length=256,
        description="Identifier of the Firestore patient document to anonymize.",
    ),
]


@router.post(
    "/collections/{collection}/documents/{document_id}",
    status_code=status.HTTP_202_ACCEPTED,
)
async def anonymize_document(
    collection: CollectionParam,
    document_id: DocumentParam,
) -> dict[str, Any]:
    """Fetch, anonymize, and persist a Firestore patient document."""

    collection_token = collection.strip()
    document_token = document_id.strip()
    if not collection_token or not document_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Collection and document identifiers must be non-empty strings.",
        )

    try:
        patient_id = await process_patient(collection_token, document_token)
    except PatientNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient document could not be found for the supplied identifiers.",
        ) from exc
    except DuplicatePatientError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An anonymized patient record already exists for this document.",
        ) from exc
    except ServiceConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="The anonymizer service is not properly configured to process patients.",
        ) from exc
    except PatientProcessingError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="The patient document could not be processed due to an upstream error.",
        ) from exc

    summary = summarize_transformations([])
    summary_payload = {
        "recordId": str(patient_id),
        "transformations": summary,
    }

    logger.info(
        "Accepted anonymizer request for processing.",
        event="anonymizer.document.accepted",
        request=scrub_for_logging(
            {
                "collection": collection_token,
                "document_id": document_token,
                "collection_length": len(collection_token),
                "document_id_length": len(document_token),
            },
            allow_keys={"collection_length", "document_id_length"},
        ),
        response=scrub_for_logging(summary_payload, allow_keys={"recordId", "status"}),
    )

    return {
        "status": "accepted",
        "summary": summary_payload,
    }

# Placeholder routers for anonymization endpoints will be added here in the future.
app.include_router(router)


__all__ = ["app", "health"]
