# Generator Service

The generator service orchestrates prompt execution and persistence for synthetic EHR
content. It exposes a FastAPI application and relies on shared LLM adapters for model
access and streaming outputs.

## Environment Variables

| Variable | Required | Description |
| --- | --- | --- |
| `GENERATOR__POSTGRES__DSN` | No (defaults to `postgresql://postgres:postgres@localhost:5432/generator`) | Database connection string used for generator persistence. |
| `GENERATOR__STORAGE__GCS_BUCKET` | No (defaults to unset) | Google Cloud Storage bucket that receives generated artifacts; leave unset to keep uploads disabled for dry-run workflows. |
| `GENERATOR__STORAGE__GCS_PREFIX` | No (defaults to unset) | Optional key prefix applied when writing to the configured bucket. |
| `GENERATOR__MODEL_OVERRIDES__PROVIDER` | No (defaults to shared model defaults) | Overrides the LLM provider used for generation. |
| `GENERATOR__MODEL_OVERRIDES__NAME` | No (defaults to shared model defaults) | Overrides the model name passed to the selected provider. |
| `GENERATOR__MODEL_OVERRIDES__TEMPERATURE` | No (defaults to unset) | Float temperature override applied when invoking the LLM (0.0–2.0). |
| `GENERATOR__RNG_SEED` | No (defaults to unset) | Optional random seed that makes sampling steps deterministic for repeatable dry-runs. |
| `OPENAI_API_KEY` | Yes when using OpenAI providers | Shared API key used by the OpenAI adapter; required to call OpenAI-hosted models. |
| `OPENAI_ORGANIZATION` | No | Optional OpenAI organization identifier shared across services. |
| `OPENAI_PROJECT` | No | Optional OpenAI project identifier shared across services. |
| `OPENAI_BASE_URL` | No | Optional base URL override for OpenAI-compatible endpoints (shared configuration). |

The generator settings use nested environment variables with `__` delimiters, so any of
the `GENERATOR__*` keys can also be supplied through a `.env` file or process
environment. LLM credentials (`OPENAI_*`) are read from the shared configuration module,
ensuring the same secrets power other services without duplication. Leaving the GCS
bucket unset keeps the service in a dry-run mode where generated payloads stay local
until you are ready to enable uploads.
