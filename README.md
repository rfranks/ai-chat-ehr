# ai-chat-ehr

Proving Grounds for ChatEHR

## Overview

`ai-chat-ehr` is a collection of FastAPI services that orchestrate language-model
powered clinical workflows. The stack bundles separate services for managing
prompt templates, retrieving patient context, and executing prompt chains against
configurable LLM providers. Each service can be run independently for focused
experimentation or together via Docker Compose for an end-to-end chat
experience.

## Service overview

| Service | Purpose | Default port | Swagger UI | OpenAPI spec |
| --- | --- | --- | --- | --- |
| API gateway | Reverse proxy that fronts the prompt, patient, and chain services with consistent observability and health checks. | 8000 | <http://localhost:8000/docs> | [`docs/openapi/api_gateway.json`](docs/openapi/api_gateway.json) |
| Prompt catalog | Hosts reusable prompt templates and simple search endpoints. | 8001 | <http://localhost:8001/docs> | [`docs/openapi/prompt_catalog.json`](docs/openapi/prompt_catalog.json) |
| Patient context | Serves mock EMR data and pre-normalised patient context payloads. | 8002 | <http://localhost:8002/docs> | [`docs/openapi/patient_context.json`](docs/openapi/patient_context.json) |
| Chain executor | Resolves prompt chains, enriches them with patient context, and executes LLM calls with optional streaming. | 8003 | <http://localhost:8003/docs> | [`docs/openapi/chain_executor.json`](docs/openapi/chain_executor.json) |

The OpenAPI documents above are generated from the live FastAPI applications and
can be imported into tooling such as Postman or Stoplight. See
[`docs/architecture.md`](docs/architecture.md) for a deeper dive into the orchestration
strategy, provider selection, and prompt categorisation logic.

## Bundled prompt catalog

The prompt catalog service ships with reusable templates that cover common
clinical workflows. Each prompt includes category labels so downstream services
can request the right slices of patient context.

| Key | Title | Description | Categories |
| --- | --- | --- | --- |
| `patient_context` | Patient Context Overview | Summarise clinical background and social determinants for the visit. | patientDetail, problems, socialHistory, careTeam |
| `clinical_plan` | Clinical Plan Outline | Draft a multi-domain assessment and plan from encounter details. | problems, orders, medications, labs, testResults |
| `follow_up_questions` | Follow-up Question Suggestions | Propose clarifying follow-up questions based on open issues. | notes, problems, patientDetail |
| `patient_summary` | Comprehensive Patient Summary | Combine demographics, active problems, and recent findings into a cohesive narrative. | patientDetail, problems, notes |
| `differential_diagnosis` | Differential Diagnosis Explorer | Prioritise differentials with supporting evidence and recommended workup. | problems, labs, testResults, notes |
| `patient_education` | Patient Education Brief | Translate the care plan into accessible counselling points and safety advice. | medications, carePlans, socialHistory |
| `safety_checks` | Care Safety Checklist | Flag medication, allergy, and monitoring concerns requiring action. | medications, allergies, vitals, orders |
| `triage_assessment` | Urgency Triage Assessment | Evaluate visit urgency from presenting symptoms, vitals, and risk factors. | vitals, patientDetail, riskScores, encounters |

## Environment setup

### Configure environment variables

1. Copy the example configuration and adjust it for your environment:
   ```bash
   cp .env.example .env
   ```
2. Populate provider credentials (for OpenAI, Azure, Anthropic, or Vertex) and
   update any overrides such as `DEFAULT_MODEL__PROVIDER` or Redis settings.

### Option A: Local Python environment

1. Create and activate a Python 3.10 virtual environment.
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
2. Install the project in editable mode to pull in service dependencies.
   ```bash
   pip install -e .
   ```
3. Launch individual services with Uvicorn as needed:
   ```bash
   uvicorn services.prompt_catalog.app:app --reload --port 8001
   uvicorn services.patient_context.app:app --reload --port 8002
   uvicorn services.chain_executor.app:app --reload --port 8003
   uvicorn services.api_gateway.app:app --reload --port 8000
   ```

### Option B: Docker Compose stack

1. Build the shared base image (only required the first time or after Dockerfile changes):
   ```bash
   docker build -f Dockerfile.base -t ai-chat-ehr-base .
   ```
2. Start the prompt catalog, patient context, chain executor, and Redis services:
   ```bash
   docker compose up --build
   ```
   The containers expose the service ports listed above on `localhost`. Use
   `docker compose down` to stop the stack when you finish testing.

## Request examples

With the stack running locally, the following `curl` snippets exercise the core
services:

* List all prompts in the catalog:
  ```bash
  curl http://localhost:8001/prompts | jq
  ```
* Filter prompts by category slug (case-insensitive) or combine with free-text query terms:
  ```bash
  curl -X POST http://localhost:8001/prompts/search \
    -H "Content-Type: application/json" \
    -d '{"categories": ["labs"], "query": "plan"}' | jq
  ```
* Discover the canonical prompt categories exposed by the catalog service:
  ```bash
  curl http://localhost:8001/categories | jq
  ```
  Each category includes a ``slug``, ``name``, ``description``, and recognised ``aliases``.
* Retrieve patient context for the bundled sample patient (`patient_id=123456`):
  ```bash
  curl "http://localhost:8002/patients/123456/context" | jq
  ```
* Include one or more `categories` query parameters to filter the response to
  specific data domains (for example, only labs and the care team):
  ```bash
  curl "http://localhost:8002/patients/123456/context?categories=labs&categories=careTeam" | jq
  ```
* Discover available LLM providers and metadata from the chain executor service:
  ```bash
  curl http://localhost:8003/chains/models | jq
  ```
* Execute a two-step chain that pulls patient context and drafts a clinical plan:
  ```bash
  curl -X POST http://localhost:8003/chains/execute \
    -H "Content-Type: application/json" \
    -d '{
          "chain": ["patient_context", "clinical_plan"],
          "patientId": "123456",
          "variables": {
            "patient_background": "Hypertension follow up visit for Ava Thompson.",
            "encounter_overview": "Review vitals and adjust medications as needed."
          },
          "modelProvider": "openai/gpt-4o-mini"
        }' | jq
  ```
* Stream chain output as server-sent events (SSE):
  ```bash
  curl -N http://localhost:8003/chains/execute/stream \
    -H "Accept: text/event-stream" \
    -H "Content-Type: application/json" \
    -d '{
          "chain": ["follow_up_questions"],
          "patientId": "123456",
          "variables": {
            "patient_summary": "Summarise outstanding questions for the follow-up visit."
          }
        }'
  ```
* Check the gateway health endpoint (when the API gateway is running):
  ```bash
  curl http://localhost:8000/health | jq
  ```

These examples demonstrate the canonical request payload shapes; refer to the
OpenAPI documentation for complete request/response schemas and error details.

## Patient fixtures

Mock EMR data that powers the patient context service lives in
[`repositories/fixtures/patients/`](repositories/fixtures/patients/). Each
patient consists of two JSON documents named with the pattern
`<patient_id>_record.json` and `<patient_id>_context.json`. To add an additional
fixture:

1. Copy the existing files as a template and update the payloads with the new
   patient's data. Both files must contain a `demographics.patientId` field that
   matches the identifier embedded in the filename.
2. Run `pytest` to validate that the loader can parse the new files.

The Docker images copy the entire `repositories/` directory (`COPY repositories
./repositories`), so any JSON fixtures committed to source control are bundled
automatically.
