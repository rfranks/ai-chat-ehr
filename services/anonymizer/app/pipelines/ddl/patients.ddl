CREATE TABLE anonymized_patients (
    document_id TEXT PRIMARY KEY,
    collection TEXT,
    firestore_document JSONB NOT NULL,
    normalized_document JSONB NOT NULL,
    patient_payload JSONB NOT NULL,
    anonymized_payload JSONB NOT NULL,
    processed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
