"""FastAPI application providing anonymization capabilities."""

from __future__ import annotations

from typing import Any, Annotated, Mapping
from uuid import NAMESPACE_URL, uuid5

from fastapi import APIRouter, FastAPI, HTTPException, Path, Request, status
from fastapi.responses import JSONResponse

from shared.http.errors import ProblemDetails, register_exception_handlers
from shared.observability.logger import configure_logging, get_logger
from shared.observability.middleware import (
    CorrelationIdMiddleware,
    RequestTimingMiddleware,
)

from services.anonymizer.logging_utils import scrub_for_logging
from services.anonymizer.reporting import summarize_transformations
from services.anonymizer.schemas import (
    AnonymizeResponse,
    TransformationAggregates,
    TransformationSummary,
)
from services.anonymizer.service import (
    DuplicatePatientError,
    PatientNotFoundError,
    PatientProcessingError,
    ServiceConfigurationError,
    process_patient,
)


logger = get_logger(__name__)

SERVICE_NAME = "anonymizer"

configure_logging(service_name=SERVICE_NAME)

logger = get_logger(__name__)

app = FastAPI(title="Anonymizer Service")
router = APIRouter(prefix="/anonymizer", tags=["anonymizer"])

app.add_middleware(RequestTimingMiddleware)
app.add_middleware(CorrelationIdMiddleware)
register_exception_handlers(app)


def _document_surrogate_id(path_params: Mapping[str, Any]) -> str | None:
    """Return a deterministic surrogate identifier for the requested document."""

    document_id = path_params.get("document_id")
    if not isinstance(document_id, str):
        return None

    token = document_id.strip()
    if not token:
        return None

    surrogate_uuid = uuid5(NAMESPACE_URL, f"https://chatehr.ai/anonymizer/document/{token}")
    return f"doc-{surrogate_uuid}"


def _problem_response(
    *,
    request: Request,
    status_code: int,
    title: str,
    detail: str,
    type_uri: str,
    extras: Mapping[str, Any] | None = None,
) -> JSONResponse:
    problem = ProblemDetails(
        type=type_uri,
        title=title,
        status=status_code,
        detail=detail,
        instance=str(request.url),
        **(extras or {}),
    )
    payload = problem.model_dump(mode="json", exclude_none=True)
    return JSONResponse(payload, status_code=status_code)


@app.exception_handler(PatientNotFoundError)
async def handle_patient_not_found(
    request: Request, exc: PatientNotFoundError
) -> JSONResponse:
    """Return a sanitized 404 response when a patient document is missing."""

    surrogate_id = _document_surrogate_id(request.path_params)
    extras: dict[str, Any] = {}
    detail = "Patient document could not be found for the supplied identifiers."
    if surrogate_id:
        extras["documentSurrogateId"] = surrogate_id
        detail = (
            "Patient document with surrogate identifier "
            f"'{surrogate_id}' could not be found."
        )

    return _problem_response(
        request=request,
        status_code=status.HTTP_404_NOT_FOUND,
        title="Patient Document Not Found",
        detail=detail,
        type_uri="https://chatehr.ai/problems/anonymizer/patient-not-found",
        extras=extras,
    )


@app.exception_handler(DuplicatePatientError)
async def handle_duplicate_patient(
    request: Request, exc: DuplicatePatientError
) -> JSONResponse:
    """Return a sanitized 409 response when a duplicate patient is detected."""

    surrogate_id = _document_surrogate_id(request.path_params)
    extras: dict[str, Any] = {}
    detail = "An anonymized patient record already exists for this document."
    if surrogate_id:
        extras["documentSurrogateId"] = surrogate_id
        detail = (
            "An anonymized patient record already exists for document surrogate "
            f"'{surrogate_id}'."
        )

    return _problem_response(
        request=request,
        status_code=status.HTTP_409_CONFLICT,
        title="Duplicate Patient Document",
        detail=detail,
        type_uri="https://chatehr.ai/problems/anonymizer/duplicate-patient",
        extras=extras,
    )


@app.exception_handler(ServiceConfigurationError)
async def handle_service_configuration(
    request: Request, exc: ServiceConfigurationError
) -> JSONResponse:
    """Return a sanitized 500 response when dependencies are misconfigured."""

    logger.exception("service_configuration_error", error=str(exc))

    detail = "The anonymizer service is misconfigured and cannot process requests."
    return _problem_response(
        request=request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        title="Anonymizer Service Misconfiguration",
        detail=detail,
        type_uri="https://chatehr.ai/problems/anonymizer/service-misconfiguration",
    )


@app.exception_handler(PatientProcessingError)
async def handle_patient_processing(
    request: Request, exc: PatientProcessingError
) -> JSONResponse:
    """Return a sanitized response for generic patient processing failures."""

    surrogate_id = _document_surrogate_id(request.path_params)
    extras: dict[str, Any] = {}
    detail = "The patient document could not be processed due to an upstream error."
    if surrogate_id:
        extras["documentSurrogateId"] = surrogate_id
        detail = (
            f"The patient document surrogate '{surrogate_id}' could not be processed "
            "due to an upstream error."
        )

    status_code = status.HTTP_502_BAD_GATEWAY
    return _problem_response(
        request=request,
        status_code=status_code,
        title="Patient Processing Error",
        detail=detail,
        type_uri="https://chatehr.ai/problems/anonymizer/patient-processing",
        extras=extras,
    )


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
    response_model=AnonymizeResponse,
)
async def anonymize_document(
    collection: CollectionParam,
    document_id: DocumentParam,
) -> AnonymizeResponse:
    """Fetch, anonymize, and persist a Firestore patient document."""

    collection_token = collection.strip()
    document_token = document_id.strip()
    if not collection_token or not document_token:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Collection and document identifiers must be non-empty strings.",
        )

    patient_id, transformation_events = await process_patient(collection_token, document_token)

    transformation_summary = summarize_transformations(transformation_events)
    aggregates = TransformationAggregates.model_validate(transformation_summary)
    response_payload = AnonymizeResponse(
        status="accepted",
        summary=TransformationSummary(record_id=patient_id, transformations=aggregates),
    )

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
        response=scrub_for_logging(
            response_payload.model_dump(by_alias=True),
            allow_keys={"recordId", "status"},
        ),
    )

    return response_payload

# Placeholder routers for anonymization endpoints will be added here in the future.
app.include_router(router)


__all__ = ["app", "health"]
