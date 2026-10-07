-- 002_schema.sql
-- Core tables: chunks (vector + text) and employee_records (structured).
-- Both carry tenant_id + allowed_principals for ACL enforcement.

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id         SERIAL PRIMARY KEY,
    source_doc_id    TEXT                NOT NULL,
    source_type      TEXT                NOT NULL,  -- 'pdf', 'ocr', 'db'
    raw_text         TEXT                NOT NULL,  -- literal extracted text, not paraphrase
    exact_locator    JSONB,                         -- page+bbox | image+region | table+row+col
    embedding        VECTOR(384),
    tenant_id        INTEGER             NOT NULL,
    allowed_principals TEXT[],
    created_at       TIMESTAMPTZ         DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS employee_records (
    record_id          SERIAL PRIMARY KEY,
    source_doc_id      TEXT                NOT NULL,
    source_type        TEXT                NOT NULL DEFAULT 'db',
    raw_text           TEXT                NOT NULL,
    exact_locator      JSONB,
    tenant_id          INTEGER             NOT NULL,
    allowed_principals TEXT[],
    employee_name      TEXT,
    field_name         TEXT,
    field_value        TEXT,
    created_at         TIMESTAMPTZ         DEFAULT NOW()
);

-- HNSW index for approximate nearest-neighbor vector search
CREATE INDEX IF NOT EXISTS idx_chunks_embedding
    ON chunks USING HNSW (embedding vector_cosine_ops);

CREATE INDEX IF NOT EXISTS idx_chunks_tenant
    ON chunks (tenant_id);

CREATE INDEX IF NOT EXISTS idx_chunks_allowed_principals
    ON chunks USING GIN (allowed_principals);

CREATE INDEX IF NOT EXISTS idx_employee_records_tenant
    ON employee_records (tenant_id);

CREATE INDEX IF NOT EXISTS idx_employee_records_principals
    ON employee_records USING GIN (allowed_principals);
