# Anonymizer Development Guide

This guide explains how to set up the anonymizer service for local development, configure runtime options, run the HTTP server, exercise its endpoints, and understand the built-in anonymization policies.

## Local setup

### Prerequisites

* Python 3.10 or newer.
* Poetry or pip for dependency installation.
* A running PostgreSQL instance (local Docker container works well).
* Access to Google Firestore or the Firestore emulator when you want to pull real documents. The service can be stubbed in tests, but live runs require `google-cloud-firestore`.

### Install dependencies

1. Create a virtual environment and activate it:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install the project in editable mode so that shared packages and the anonymizer code are available:
   ```bash
   pip install -e .
   ```
3. Add optional dependencies that the anonymizer uses when integrating with Firestore and PostgreSQL:
   ```bash
   pip install google-cloud-firestore asyncpg
   ```
   Presidio is already pulled in via the core project dependencies (`presidio-analyzer`) and powers the PHI recognizers used during anonymization.【F:pyproject.toml†L27-L52】【F:services/anonymizer/app/clients/firestore_client.py†L74-L97】

### Seed supporting services

* **PostgreSQL** – Create a database (defaults to `anonymizer`) and apply the DDL shipped with the service. The default mapping writes to `anonymized_patients` as declared in [`services/anonymizer/app/pipelines/ddl/patients.ddl`](../../services/anonymizer/app/pipelines/ddl/patients.ddl). The table stores the raw Firestore payload, its normalized variant, the extracted patient payload, and the anonymized patient data alongside the originating collection and processing timestamp so downstream analytics can inspect each stage of the pipeline.【F:services/anonymizer/app/pipelines/ddl/patients.ddl†L1-L8】
* **Firestore** – Populate a `patients` collection with documents that contain a `patient` object shaped like `PatientRecord`. The pipeline normalizes documents and extracts the payload using the shared model definitions.【F:services/anonymizer/app/pipelines/patient_pipeline.py†L343-L367】【F:shared/models/chat.py†L334-L377】

For local testing you can point the service at the Firestore emulator by exporting the standard Google environment variables alongside the anonymizer-specific settings.

## Environment variables

Settings are organized into nested sections. Each value can be provided with an `ANONYMIZER_`-prefixed variable or a short alias (shown in parentheses).

| Variable | Default | Description |
| --- | --- | --- |
| `ANONYMIZER_SERVICE_NAME` (`SERVICE_NAME`) | `anonymizer` | Human-friendly name emitted in logs and audit events.【F:services/anonymizer/app/config/settings.py†L16-L33】 |
| `ANONYMIZER_HOST` (`HOST`) | `0.0.0.0` | Interface bound by the FastAPI server.【F:services/anonymizer/app/config/settings.py†L23-L33】 |
| `ANONYMIZER_PORT` (`PORT`) | `8004` | HTTP port exposed by the service.【F:services/anonymizer/app/config/settings.py†L23-L33】 |
| `ANONYMIZER_DB_URL` (`DATABASE_URL`) | `postgresql+asyncpg://anonymizer:anonymizer@localhost:5432/anonymizer` | SQLAlchemy-compatible PostgreSQL URL used by the repository layer.【F:services/anonymizer/app/config/settings.py†L35-L55】 |
| `ANONYMIZER_LOG_LEVEL` (`LOG_LEVEL`) | `info` | Log verbosity (`debug`, `info`, etc.).【F:services/anonymizer/app/config/settings.py†L57-L71】 |
| `ANONYMIZER_LOG_JSON` (`LOG_JSON`) | `true` | Emit structured JSON logs when set to `true`. Set to `false` for local readability.【F:services/anonymizer/app/config/settings.py†L57-L71】 |
| `ANONYMIZER_FIRESTORE_PROJECT_ID` (`FIRESTORE_PROJECT_ID`) | `None` | Google Cloud project used when instantiating the Firestore client.【F:services/anonymizer/app/config/settings.py†L73-L113】 |
| `ANONYMIZER_FIRESTORE_COLLECTION` (`FIRESTORE_COLLECTION`) | `patients` | Default Firestore collection holding patient documents.【F:services/anonymizer/app/config/settings.py†L73-L113】 |
| `ANONYMIZER_FIRESTORE_CREDENTIALS_PATH` (`FIRESTORE_CREDENTIALS_PATH`) | `None` | Path to a service account JSON key. Mutually exclusive with `*_CREDENTIALS_INFO`.【F:services/anonymizer/app/config/settings.py†L73-L113】 |
| `ANONYMIZER_PIPELINE_DDL_DIRECTORY` (`PIPELINE_DDL_DIRECTORY`) | `<repo>/services/anonymizer/app/pipelines/ddl` | Directory scanned for `.ddl` files that define INSERT statements.【F:services/anonymizer/app/config/settings.py†L115-L158】【F:services/anonymizer/app/main.py†L37-L71】 |
| `ANONYMIZER_PIPELINE_INCLUDE_DEFAULTED` (`PIPELINE_INCLUDE_DEFAULTED`) | `false` | Include columns with database defaults when rendering INSERT statements.【F:services/anonymizer/app/config/settings.py†L115-L158】 |
| `ANONYMIZER_PIPELINE_INCLUDE_NULLABLE` (`PIPELINE_INCLUDE_NULLABLE`) | `true` | Include nullable columns during INSERT rendering.【F:services/anonymizer/app/config/settings.py†L115-L158】 |
| `ANONYMIZER_PIPELINE_RETURNING` (`PIPELINE_RETURNING`) | `{}` | Optional mapping that declares additional `RETURNING` clauses. Supply as JSON, e.g. `{"patients": ["id"]}`.【F:services/anonymizer/app/config/settings.py†L115-L158】 |
| `ANONYMIZER_PIPELINE_PATIENT_COLLECTION` (`PIPELINE_PATIENT_COLLECTION`) | `patients` | Firestore collection consulted by the patient pipeline.【F:services/anonymizer/app/config/settings.py†L115-L158】 |
| `ANONYMIZER_PIPELINE_PATIENT_DDL_KEY` (`PIPELINE_PATIENT_DDL_KEY`) | `patients` | Key in the DDL mapping used when persisting anonymized payloads.【F:services/anonymizer/app/config/settings.py†L115-L158】【F:services/anonymizer/app/main.py†L80-L115】 |

The service automatically loads `.env` at startup and supports the nested `SECTION__FIELD` notation (for example, `ANONYMIZER__DATABASE__URL`).【F:services/anonymizer/app/config/settings.py†L160-L187】

## Running the server

### Direct Uvicorn

```bash
uvicorn services.anonymizer.main:app \
  --host ${ANONYMIZER_HOST:-0.0.0.0} \
  --port ${ANONYMIZER_PORT:-8004} \
  --reload
```

The `create_app` factory wires together the Firestore client, PostgreSQL repository, and patient pipeline. It also sets up structured audit logging for each anonymization request.【F:services/anonymizer/app/main.py†L1-L222】

### Docker Compose

The repository provides a compose target that builds the anonymizer image and connects it to supporting services such as PostgreSQL. Run:

```bash
docker compose up anonymizer postgres --build
```

The anonymizer container exposes port `8004` and reads the same environment variables documented above via the compose file defaults.【F:docker-compose.yml†L70-L111】

## Sample request/response

When the service runs locally you can hit the primary endpoint that anonymizes Firestore-backed patient documents. Replace `doc-123` with a valid document ID in your collection.

```bash
curl -X POST "http://localhost:8004/anonymize/patients/doc-123" \
  -H "Accept: application/json"
```

A successful response includes the anonymized patient payload, counts of replacements applied for each entity type, and rows persisted to PostgreSQL:

```json
{
  "documentId": "doc-123",
  "collection": "patients",
  "anonymizedPatient": {
    "foo": "bar"
  },
  "anonymization": {
    "totalReplacements": 2,
    "entities": [
      { "entityType": "PERSON", "count": 2 }
    ]
  },
  "repository": {
    "rows": [
      { "id": 1 }
    ],
    "count": 1
  }
}
```

If the requested document cannot be found, the service returns a `404` with a descriptive message. Unexpected errors are surfaced as `500` responses with a generic failure string, while detailed diagnostics land in the structured logs.【F:services/anonymizer/app/main.py†L120-L222】【F:services/anonymizer/tests/test_main.py†L18-L104】

## Anonymization rules

The patient pipeline applies deterministic replacements using Microsoft Presidio recognizers and a set of field-level rules:

* **Field coverage** – By default the pipeline redacts demographic names, address, phone, email, MRN, care team names, encounter providers, facility names, and note authors. Wildcard rules (`*`) ensure that nested arrays such as care team members and clinical notes are processed consistently.【F:services/anonymizer/app/pipelines/patient_pipeline.py†L240-L318】
* **Replacement engine** – Detected entities are replaced via `ReplacementContext`, which hashes original values and ensures the same placeholder is reused for identical inputs during a request. This avoids leaking raw PHI while keeping cross-field consistency.【F:services/anonymizer/app/pipelines/patient_pipeline.py†L191-L238】
* **Audit trail** – For each request the pipeline aggregates replacement counts and the API emits an audit entry noting the entity types removed and persistence status.【F:services/anonymizer/app/pipelines/patient_pipeline.py†L336-L409】【F:services/anonymizer/app/main.py†L142-L214】

For a comprehensive view of the PHI catalog, detection techniques, and the Safe Harbor mapping that underpins these defaults, see [`docs/anonymizer/phi_catalog.md`](phi_catalog.md).【F:docs/anonymizer/phi_catalog.md†L1-L66】 The anonymizer architecture document covers integration points and control-plane practices for extending or hardening these rules in more detail ([`docs/anonymizer/architecture.md`](architecture.md)).【F:docs/anonymizer/architecture.md†L1-L48】

## Next steps

* Add new field rules by passing a custom sequence of `FieldRule` objects into `PatientPipeline` or by extending the default list.
* Provide additional DDL mappings when persisting more than one table. Update `ANONYMIZER_PIPELINE_RETURNING` as needed to capture generated identifiers.
* Integrate with your monitoring stack by subscribing to the structured logs emitted by `record_anonymization_audit`.
