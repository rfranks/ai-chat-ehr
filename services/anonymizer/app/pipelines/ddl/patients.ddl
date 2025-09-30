CREATE TABLE anonymized_patients (
    document_id TEXT PRIMARY KEY,
    anonymized_payload JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
