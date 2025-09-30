"""FastAPI application entrypoint for the anonymizer service."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping, Union

from fastapi import APIRouter, Depends, FastAPI, HTTPException, status
from fastapi.encoders import jsonable_encoder

from .clients import FirestoreClient, FirestoreClientConfig
from .clients.postgres_repository import InsertStatement, PostgresRepository
from .config import AppSettings, Settings, get_settings
from .logging import (
    ReplacementAuditEntry,
    anonymizer_logging_context,
    configure_logging,
    get_logger,
    record_anonymization_audit,
)
from .pipelines import build_mapping_from_files
from .pipelines.patient_pipeline import (
    PatientDocumentNotFoundError,
    PatientPipeline,
)

AppConfig = Union[Settings, AppSettings]

logger = get_logger(__name__)


def _extract_app_settings(settings: AppConfig) -> AppSettings:
    """Normalise either top-level or app-only settings objects."""

    if isinstance(settings, Settings):
        return settings.app

    return settings


def _discover_ddl_files(directory: str) -> list[Path]:
    path = Path(directory)
    if not path.exists():
        raise RuntimeError(f"DDL directory '{directory}' does not exist.")
    ddl_files = sorted(file for file in path.glob("*.ddl") if file.is_file())
    if not ddl_files:
        raise RuntimeError(f"No .ddl files found in '{directory}'.")
    return ddl_files


@lru_cache
def _load_ddl_mapping() -> dict[str, InsertStatement]:
    settings = get_settings()
    ddl_files = _discover_ddl_files(settings.pipeline.ddl_directory)
    returning = (
        {key: tuple(value) for key, value in settings.pipeline.returning.items()}
        if settings.pipeline.returning
        else None
    )
    return build_mapping_from_files(
        ddl_files,
        include_defaulted=settings.pipeline.include_defaulted,
        include_nullable=settings.pipeline.include_nullable,
        returning=returning,
    )


@lru_cache
def _get_postgres_repository() -> PostgresRepository:
    settings = get_settings()
    mapping = _load_ddl_mapping()
    return PostgresRepository(settings.database.url, mapping)


@lru_cache
def _get_firestore_client() -> FirestoreClient:
    settings = get_settings()
    firestore_settings = settings.firestore
    config = FirestoreClientConfig(
        project_id=firestore_settings.project_id,
        default_collection=firestore_settings.default_collection,
        credentials_path=firestore_settings.credentials_path,
        credentials_info=firestore_settings.credentials_info,
    )
    return FirestoreClient(config=config)


def _resolve_anonymized_payload(
    payload: Mapping[str, Any], _context: Any
) -> Mapping[str, Any]:
    return payload


def _resolve_collection(_payload: Mapping[str, Any], context: Any) -> str | None:
    return getattr(context, "collection", None)


def _resolve_firestore_document(
    _payload: Mapping[str, Any], context: Any
) -> Mapping[str, Any]:
    return getattr(context, "firestore_document", {})


def _resolve_normalized_document(
    _payload: Mapping[str, Any], context: Any
) -> Mapping[str, Any]:
    return getattr(context, "normalized_document", {})


def _resolve_patient_payload(
    _payload: Mapping[str, Any], context: Any
) -> Mapping[str, Any]:
    return getattr(context, "patient_payload", {})


@lru_cache
def _build_patient_pipeline() -> PatientPipeline:
    settings = get_settings()
    column_mapping = {
        "document_id": "document_id",
        "collection": _resolve_collection,
        "firestore_document": _resolve_firestore_document,
        "normalized_document": _resolve_normalized_document,
        "patient_payload": _resolve_patient_payload,
        "anonymized_payload": _resolve_anonymized_payload,
    }
    return PatientPipeline(
        firestore_client=_get_firestore_client(),
        repository=_get_postgres_repository(),
        ddl_key=settings.pipeline.patient_ddl_key,
        column_mapping=column_mapping,
    )


async def get_patient_pipeline() -> PatientPipeline:
    """Return a cached patient pipeline instance for request handlers."""

    return _build_patient_pipeline()


def create_app(settings: AppConfig | None = None) -> FastAPI:
    """Create and configure the FastAPI application instance."""

    resolved_settings = settings or get_settings()
    app_settings = _extract_app_settings(resolved_settings)

    if isinstance(resolved_settings, Settings):
        configure_logging(
            service_name=app_settings.service_name,
            level=resolved_settings.logging.level,
        )
    else:
        configure_logging(service_name=app_settings.service_name)

    application = FastAPI(title="Anonymizer Service")

    router = APIRouter()

    @router.get("/health", summary="Service health check")
    async def health() -> dict[str, str]:
        """Return a simple health status payload for uptime monitoring."""

        return {"status": "ok", "service": app_settings.service_name}

    @router.post(
        "/anonymize/patients/{document_id}",
        summary="Anonymize a patient document from Firestore.",
    )
    async def anonymize_patient(  # noqa: D417 - FastAPI dependency injection
        document_id: str,
        pipeline: PatientPipeline = Depends(get_patient_pipeline),
        settings: Settings = Depends(get_settings),
    ) -> dict[str, Any]:
        """Run the patient anonymization pipeline and return a summary payload."""

        collection = settings.pipeline.patient_collection
        with anonymizer_logging_context(
            document_id=document_id, collection=collection
        ) as correlation_id:
            try:
                summary = await pipeline.run_with_summary(
                    document_id, collection=collection
                )
            except PatientDocumentNotFoundError as exc:
                logger.info(
                    "patient_document_not_found",
                    document_id=document_id,
                    collection=collection,
                    correlation_id=correlation_id,
                )
                record_anonymization_audit(
                    document_id=document_id,
                    collection=collection,
                    actor=app_settings.service_name,
                    status="not_found",
                    total_replacements=0,
                    correlation_id=correlation_id,
                    metadata={"error": str(exc)},
                )
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"message": str(exc), "documentId": exc.document_id},
                ) from exc
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception(
                    "patient_anonymization_failed",
                    document_id=document_id,
                    collection=collection,
                    correlation_id=correlation_id,
                    error=str(exc),
                )
                record_anonymization_audit(
                    document_id=document_id,
                    collection=collection,
                    actor=app_settings.service_name,
                    status="error",
                    total_replacements=0,
                    correlation_id=correlation_id,
                    metadata={"error": str(exc)},
                )
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to anonymize patient document.",
                ) from exc

            anonymized_payload = jsonable_encoder(summary.anonymized_patient)
            replacement_entries = [
                ReplacementAuditEntry(
                    entity_type=item.entity_type, count=item.count
                )
                for item in summary.replacements
            ]
            total_replacements = sum(entry.count for entry in replacement_entries)
            repository_rows = jsonable_encoder(list(summary.repository_results))

            response = {
                "documentId": summary.document_id,
                "collection": summary.collection or collection,
                "anonymizedPatient": anonymized_payload,
                "anonymization": {
                    "totalReplacements": total_replacements,
                    "entities": [
                        entry.to_dict() for entry in replacement_entries
                    ],
                },
                "repository": {
                    "rows": repository_rows,
                    "count": len(repository_rows),
                },
            }

            logger.info(
                "patient_anonymized",
                document_id=summary.document_id,
                collection=response["collection"],
                correlation_id=correlation_id,
                total_replacements=total_replacements,
            )

            record_anonymization_audit(
                document_id=summary.document_id,
                collection=response["collection"],
                actor=app_settings.service_name,
                status="success",
                total_replacements=total_replacements,
                replacements=replacement_entries,
                correlation_id=correlation_id,
                metadata={"repositoryRowCount": len(repository_rows)},
            )

        return response

    application.include_router(router)

    @application.on_event("shutdown")
    async def _shutdown_repository() -> None:
        if _get_postgres_repository.cache_info().currsize:
            repository = _get_postgres_repository()
            await repository.dispose()

    return application


settings = get_settings()
app = create_app(settings=settings)

__all__ = [
    "app",
    "settings",
    "create_app",
    "AppSettings",
    "Settings",
    "get_settings",
    "get_patient_pipeline",
]
