# Anonymizer Service

The anonymizer service extracts patient documents from Firestore, removes protected health information (PHI) according to HIPAA Safe Harbor rules, and persists de-identified rows to Postgres.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `ANONYMIZER_FIRESTORE_SOURCE` | No (defaults to `fixtures`) | Chooses the Firestore data source mode. Use `fixtures` for local JSON fixtures or `credentials` to load documents with a real Firestore client. |
| `ANONYMIZER_FIRESTORE_FIXTURES_DIR` | No | Overrides the default fixture search path when running in `fixtures` mode. Must point to a directory containing patient JSON files. |
| `ANONYMIZER_FIRESTORE_CREDENTIALS` | When `ANONYMIZER_FIRESTORE_SOURCE=credentials` | File path to Google service account credentials used by the credentialed Firestore data source. |
| `ANONYMIZER_POSTGRES_DSN` | When `ANONYMIZER_STORAGE_MODE=database` | Postgres DSN used by the storage layer for inserting anonymized patient rows. |
| `ANONYMIZER_STORAGE_MODE` | No (defaults to `database`) | Controls how anonymized rows are persisted. Use `database` to insert directly into Postgres or `sqlfile` to emit `INSERT` statements without touching the database. |
| `ANONYMIZER_STORAGE_SQL_PATH` | When `ANONYMIZER_STORAGE_MODE=sqlfile` (defaults to `anonymizer_dry_run.sql`) | Filesystem path where dry-run `INSERT` statements are written for review. |
| `ANONYMIZER_IDENTIFIER_HASH_SECRET` | No (defaults to `ai-chat-ehr-anonymizer`) | HMAC key used when deterministic identifier fallbacks are required (for example, when Presidio leaves a facility or tenant ID unchanged). |
| `ANONYMIZER_HASH_SECRET` | No (defaults to `ai-chat-ehr-safe-harbor`) | Secret fed into the Presidio hashing strategy so replacements remain deterministic across runs. |
| `ANONYMIZER_HASH_PREFIX` | No (defaults to `anon`) | Prefix prepended to Presidio-generated hash surrogates for Safe Harbor entities. |
| `ANONYMIZER_HASH_LENGTH` | No (defaults to `12`) | Truncates the hexadecimal digest that Presidio produces for entity replacements; must parse as an integer. |

Hash-related environment variables influence two different code paths. `ANONYMIZER_HASH_*` feeds the Presidio engine configuration so that recognized entities (names, phone numbers, emails, etc.) become stable `anon_<digest>` tokens, while `ANONYMIZER_IDENTIFIER_HASH_SECRET` drives the service-level HMAC fallback that pseudonymizes identifiers the analyzer leaves untouched before coercing them into UUIDs suitable for storage.【F:services/anonymizer/service.py†L45-L52】【F:services/anonymizer/service.py†L192-L237】【F:services/anonymizer/service.py†L773-L812】【F:services/anonymizer/service.py†L859-L866】【F:services/anonymizer/presidio_engine.py†L71-L77】【F:services/anonymizer/presidio_engine.py†L315-L325】 

## Fixture Workflows

The default development workflow loads documents from JSON fixtures under `services/anonymizer/firestore_fixtures/patients`. You can provide your own fixtures by setting `ANONYMIZER_FIRESTORE_FIXTURES_DIR` to a directory of `.json` files where each filename (minus extension) becomes the Firestore document ID.

When `ANONYMIZER_FIRESTORE_SOURCE=credentials`, the service instantiates a placeholder Firestore client that expects `ANONYMIZER_FIRESTORE_CREDENTIALS` to point to a service account JSON file. This path is validated before the service starts so misconfigurations fail fast.

### Fixture smoke test

The repository bundles a helper script for exercising the anonymizer against the fixture-backed Firestore data source without starting the FastAPI service. Provide the document identifier and a Postgres DSN (for example, a local dev instance) to fetch the fixture, anonymize it, and persist the resulting patient row:

```bash
python scripts/run_anonymizer.py xpF51IBED5TOKMPJamWo \
  --postgres-dsn postgresql://postgres:postgres@localhost:5432/postgres \
  --dump-summary
```

Add `--no-bootstrap-schema` when the target database already contains the anonymizer tables.

### Local CLI Workflow

Use the CLI script when you want to dry-run anonymization locally without spinning up FastAPI. Set the environment variables that mirror the production service configuration so the CLI produces the same deterministic surrogates:

```bash
export ANONYMIZER_POSTGRES_DSN="postgresql://postgres:postgres@localhost:5432/postgres"
export ANONYMIZER_FIRESTORE_FIXTURES_DIR="services/anonymizer/firestore_fixtures/patients"
export ANONYMIZER_HASH_SECRET="ai-chat-ehr-safe-harbor"
export ANONYMIZER_HASH_PREFIX="anon"
export ANONYMIZER_HASH_LENGTH="12"
export ANONYMIZER_IDENTIFIER_HASH_SECRET="ai-chat-ehr-anonymizer"
```

With the variables in place, invoke the script against the bundled sample patient fixture. The command below targets the `xpF51IBED5TOKMPJamWo.json` fixture and writes the anonymized record to the configured Postgres DSN:

```bash
python scripts/run_anonymizer.py xpF51IBED5TOKMPJamWo --postgres-dsn "$ANONYMIZER_POSTGRES_DSN" --dump-summary
```

Successful runs print the persisted patient UUID along with a JSON transformation summary so you can confirm that only hashed surrogates and Safe Harbor generalizations were emitted (for example `Persisted anonymized patient 917e452d-d44c-5f2c-9297-bf18e304cdd8`).【F:scripts/run_anonymizer.py†L71-L88】【F:services/anonymizer/firestore_fixtures/patients/xpF51IBED5TOKMPJamWo.json†L1-L66】

**Troubleshooting tips**

- Ensure the DSN points to a reachable Postgres instance; failures surface as connection errors before any patient payload is processed.【F:scripts/run_anonymizer.py†L46-L67】
- If the script reports that the fixture cannot be located, verify `ANONYMIZER_FIRESTORE_FIXTURES_DIR` includes the sample JSON and that the document ID matches the filename minus `.json`.【F:services/anonymizer/firestore/fixtures.py†L8-L56】
- Review the printed summary instead of raw logs when validating PHI handling—the CLI intentionally outputs only hashed surrogates and aggregate counts so no raw PHI ever appears on stdout.【F:scripts/run_anonymizer.py†L71-L88】【F:services/anonymizer/reporting.py†L28-L68】

## Dry-run SQL output

Set `ANONYMIZER_STORAGE_MODE=sqlfile` to review anonymized patient rows without writing
to Postgres. In this mode, the service appends `INSERT INTO patient ...` statements to
`ANONYMIZER_STORAGE_SQL_PATH` (defaulting to `anonymizer_dry_run.sql`). Developers can
inspect the generated SQL to confirm PHI Safe Harboring before allowing the records to
reach the live database. Switch the mode back to `database` once it is safe to persist
the rows directly.

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

## Generalization Rules

### Patient dates of birth

Dates of birth are reduced to the minimum granularity allowed under Safe Harbor. Patients younger than 90 are truncated to the first day of their birth year, while any patient aged 90 or older has their DOB suppressed entirely so the database never stores a day, month, or year for that individual.【F:services/anonymizer/service.py†L815-L856】 

### Coverage mailing addresses

When a coverage record contains a mailing address, the street, city, and postal code are deterministically synthesized from the original components using salted SHA-256 hashes. State abbreviations that already conform to the two-letter USPS format are preserved (and normalized to uppercase), and countries pass through unchanged so downstream systems retain high-level geography without re-identification risk.【F:services/anonymizer/service.py†L539-L755】 

### Coverage plan effective dates

Plan effective dates are converted to ISO dates if necessary and then truncated to January 1 of the original year. Inputs that cannot be parsed as real dates are discarded and logged so malformed data never propagates to storage.【F:services/anonymizer/service.py†L546-L611】 

## Transformation Summary

- Presidio replaces every detected Safe Harbor entity with a deterministic hash that adopts the configured prefix (`anon` by default) and truncation length. This ensures stable surrogates across documents without leaking the original value.【F:services/anonymizer/presidio_engine.py†L71-L77】【F:services/anonymizer/presidio_engine.py†L315-L325】 
- If Presidio leaves an identifier unchanged (for example, certain payer numbers or tenant IDs), the service applies an HMAC fallback using `ANONYMIZER_IDENTIFIER_HASH_SECRET`, records a `pseudonymize` transformation event, and then coerces the digest into a UUID before persistence.【F:services/anonymizer/service.py†L192-L237】【F:services/anonymizer/service.py†L773-L812】【F:services/anonymizer/service.py†L859-L866】 
- Deterministic street, city, and postal-code synthesis yields consistent yet fictitious mailing addresses for each coverage while retaining the original state/country context when present.【F:services/anonymizer/service.py†L539-L755】 
- Dates of birth and plan effective dates follow Safe Harbor generalization so high-risk age information never appears with day-level precision in the warehouse.【F:services/anonymizer/service.py†L546-L595】【F:services/anonymizer/service.py†L815-L856】 

## Worked Example: Fixture to Patient Row

Starting from the sample Firestore document `xpF51IBED5TOKMPJamWo.json`, which stores a 1933 birth date, Tampa mailing address, and payer effective date of 2015-04-01, the anonymizer produces the following sanitized patient record.【F:services/anonymizer/firestore_fixtures/patients/xpF51IBED5TOKMPJamWo.json†L1-L66】 

1. **Presidio hashing.** With default settings the engine rewrites personal names such as `Nick` and `Alderman` to deterministic surrogates (`anon_a639fa71ee38` and `anon_3773d139b147`, respectively), ensuring repeated references map to the same token across payloads.【F:services/anonymizer/presidio_engine.py†L71-L77】【F:services/anonymizer/presidio_engine.py†L315-L325】 
2. **Identifier fallback.** Facility, tenant, and EHR identifiers that Presidio cannot classify are run through the HMAC fallback and converted into UUIDs (`c5611650-ce3d-51a6-bd89-0e4bc902d28f` for the tenant, `917e452d-d44c-5f2c-9297-bf18e304cdd8` for the facility, and `51ba1a39-4736-57e1-8916-5e6394d9d753` for the EHR instance) so they remain unique without exposing the original strings.【F:services/anonymizer/service.py†L192-L237】【F:services/anonymizer/service.py†L773-L812】【F:services/anonymizer/service.py†L859-L866】 
3. **DOB generalization.** Because the patient is older than 90, the service omits the `dob` field entirely when constructing the Postgres row.【F:services/anonymizer/service.py†L815-L856】 
4. **Address synthesis.** The Tampa mailing address becomes the deterministic surrogate `4174 Lakeside Ave, Glenmont, FL 12790, United States`, preserving state and country while replacing the street/city/postal code trio.【F:services/anonymizer/service.py†L539-L755】 
5. **Coverage effective dates.** Each coverage plan effective date is truncated to `2015-01-01`, the first day of the original year.【F:services/anonymizer/service.py†L546-L595】 

The resulting patient row persisted to Postgres contains Safe Harbor–compliant fields such as:

```json
{
  "tenant_id": "c5611650-ce3d-51a6-bd89-0e4bc902d28f",
  "facility_id": "917e452d-d44c-5f2c-9297-bf18e304cdd8",
  "ehr_instance_id": "51ba1a39-4736-57e1-8916-5e6394d9d753",
  "ehr_external_id": "406835c1d10cf367760439765fc908199e5937e8e5115780647c637b96410826",
  "name_first": "anon_a639fa71ee38",
  "name_last": "anon_3773d139b147",
  "gender": "female",
  "status": "inactive",
  "dob": null,
  "legal_mailing_address": {
    "street": "4174 Lakeside Ave",
    "city": "Glenmont",
    "state": "FL",
    "postal_code": "12790",
    "country": "United States"
  }
}
```

All values originate from deterministic transforms, so reprocessing the fixture produces identical sanitized rows suitable for repeatable tests and delta debugging.【F:services/anonymizer/service.py†L539-L755】【F:services/anonymizer/service.py†L773-L812】【F:services/anonymizer/presidio_engine.py†L71-L77】【F:services/anonymizer/presidio_engine.py†L315-L325】 

## Additional CLI and Testing Resources

- Follow the repository-level setup guides for running services locally or via Docker Compose when you need to exercise the anonymizer FastAPI application in an end-to-end scenario.【F:README.md†L70-L122】 
- Use the project-wide testing instructions (`pytest tests/services/anonymizer`) when validating Safe Harbor changes locally; these tests cover configuration overrides, Firestore fixture loading, and reporting flows.【F:services/anonymizer/README.md†L32-L38】 
