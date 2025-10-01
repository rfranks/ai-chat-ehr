# Anonymizer Service

The anonymizer service extracts patient documents from Firestore, removes protected health information (PHI) according to HIPAA Safe Harbor rules, and persists de-identified rows to Postgres.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `ANONYMIZER_FIRESTORE_SOURCE` | No (defaults to `fixtures`) | Chooses the Firestore data source mode. Use `fixtures` for local JSON fixtures or `credentials` to load documents with a real Firestore client. |
| `ANONYMIZER_FIRESTORE_FIXTURES_DIR` | No | Overrides the default fixture search path when running in `fixtures` mode. Must point to a directory containing patient JSON files. |
| `ANONYMIZER_FIRESTORE_CREDENTIALS` | When `ANONYMIZER_FIRESTORE_SOURCE=credentials` | File path to Google service account credentials used by the credentialed Firestore data source. |
| `ANONYMIZER_POSTGRES_DSN` | Yes | Postgres DSN used by the storage layer for inserting anonymized patient rows. |

## Fixture Workflows

The default development workflow loads documents from JSON fixtures under `services/anonymizer/firestore_fixtures/patients`. You can provide your own fixtures by setting `ANONYMIZER_FIRESTORE_FIXTURES_DIR` to a directory of `.json` files where each filename (minus extension) becomes the Firestore document ID.

When `ANONYMIZER_FIRESTORE_SOURCE=credentials`, the service instantiates a placeholder Firestore client that expects `ANONYMIZER_FIRESTORE_CREDENTIALS` to point to a service account JSON file. This path is validated before the service starts so misconfigurations fail fast.

## Testing Strategy

Unit tests focus on deterministic components and can be run with:

```bash
pytest tests/services/anonymizer
```

Key coverage areas include Firestore fixture loading/validation, environment variable configuration, and reporting logic.

## Safe Harbor & PHI Handling Guidance

The Presidio anonymization engine targets the HIPAA Safe Harbor identifiers enumerated in `SAFE_HARBOR_ENTITIES`, including personal names, contact information, account numbers, and ages over 89. Deterministic hashing, redaction, and optional LLM-based synthesis are applied per entity policy to ensure that all 18 Safe Harbor identifiers are suppressed or transformed before persistence.

To maintain compliance:

- **Avoid logging PHI.** Instrumentation and debugging statements should use anonymized tokens or truncated snippets instead of raw identifiers.
- **Keep tests PHI-free.** Test fixtures should rely on synthetic patient data already provided in the repository or generated locally without referencing real individuals.
- **Document Safe Harbor assumptions.** Any new recognizers or anonymization policies must continue to cover the Safe Harbor set and document deviations in this README.

Following these practices prevents accidental disclosure of PHI in logs, test assertions, and development workflows while aligning with the Safe Harbor implementation shipped with the service.
