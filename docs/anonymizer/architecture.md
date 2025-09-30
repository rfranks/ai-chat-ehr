# Anonymizer Service Architecture

## System Goals
- Protect patient privacy by anonymizing identifiable data before downstream processing.
- Provide consistent, configurable anonymization across structured and unstructured data sources.
- Deliver low-latency anonymization suitable for real-time chat interactions and batch workflows.
- Maintain auditability, monitoring, and clear operational controls.

## Service Boundaries
- **Inputs:** Raw patient data from chat transcripts, clinical notes, metadata, and uploaded documents.
- **Outputs:** Sanitized data objects with identified PHI elements redacted, masked, or tokenized per policy.
- **Upstream Dependencies:** Ingestion services, conversation orchestrator, document upload pipelines.
- **Downstream Consumers:** LLM orchestration layer, analytics pipelines, storage services, compliance audit logs.
- **Responsibilities:** Detection, classification, and transformation of PHI; configuration management; anonymization policy enforcement; logging of anonymization actions.
- **Non-responsibilities:** Long-term storage of PHI, identity resolution, consent management, or access control for upstream systems.

## Data Flow
### Inbound
1. Ingestion services push payloads (JSON, text, binary attachments) via gRPC/REST to the anonymizer API.
2. Payload metadata (tenant, policy version, PHI sensitivity) accompanies each request for policy enforcement.
3. The service validates schema, authenticates the caller using mTLS + JWT, and queues work units for processing.

### Internal Processing
1. A dispatcher routes work to one of two anonymization pipelines:
   - **Presidio Pipeline** for deterministic pattern- and ML-based detection.
   - **LLM Pipeline** for context-aware detection and redaction.
2. Shared utilities normalize text, extract structured fields, and handle document OCR when required.
3. A policy engine selects transformations (mask, redact, tokenize, replace with category labels) per PHI type.
4. The service emits audit events (PHI found, rule applied, actor, timestamp) to the compliance log stream.

### Outbound
1. Sanitized payloads are returned synchronously for low-latency use cases or written to a message bus for asynchronous consumers.
2. Metadata includes anonymization summary (detected entities, transformations), policy version, and processing metrics.
3. Audit log records and metrics are forwarded to the observability stack (OpenTelemetry, SIEM) for monitoring and traceability.

## Anonymization Strategies
### Presidio-based Pipeline
- Uses Microsoft Presidio analyzers and recognizers customized with domain-specific patterns.
- Ensures deterministic behaviour, configurable thresholds, and lower compute cost.
- Suitable for structured data and high-confidence detections.
- Supports custom transformers (hashing, masking, format-preserving tokenization) aligned with policy.

### LLM-assisted Pipeline
- Employs fine-tuned or prompt-engineered LLMs for contextual PHI detection when deterministic methods fall short.
- Uses retrieval-augmented prompts with policy snippets and tenant configuration.
- Validates LLM outputs against allowed token transformations and cross-checks with Presidio to minimize hallucinations.
- Includes human-in-the-loop review hooks for low-confidence detections.
- Applies guardrails: toxicity filters, truncation, and redaction rules to ensure only anonymized text leaves the LLM stage.

### Pipeline Selection & Orchestration
- Policy engine selects pipeline based on data type, tenant risk profile, and latency requirements.
- Hybrid mode runs Presidio first and uses LLM only for unresolved spans to optimize cost and accuracy.
- Pipeline metrics feed back into adaptive tuning (thresholds, prompts) via configuration management.

## Secrets Management
- Secrets (API keys, certificates, Presidio custom model credentials) stored in a centralized secret manager (e.g., HashiCorp Vault, AWS Secrets Manager).
- Runtime services access secrets via short-lived tokens issued through workload identity (Kubernetes Service Accounts or cloud IAM roles).
- Secrets injected at runtime through environment variables or sidecar volume mounts; never committed to source control.
- Regular rotation policies enforced; audit logs monitor secret access.

## HIPAA Compliance Considerations
- Enforce minimum necessary principle: only PHI needed for anonymization is processed and retained temporarily in memory.
- Implement access controls and authentication for all API endpoints (mTLS, OAuth scopes per tenant).
- Maintain detailed audit trails for PHI detection and transformation actions for minimum six years.
- Encrypt data in transit (TLS 1.2+) and at rest (disk encryption for temporary storage, encrypted message queues).
- Validate and document Business Associate Agreements (BAAs) with cloud providers and third-party LLM services.
- Conduct regular risk assessments, penetration testing, and workforce training on PHI handling procedures.
- Provide incident response playbooks for anonymization failures, including notification workflows and corrective actions.

