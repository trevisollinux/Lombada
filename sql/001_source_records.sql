CREATE TABLE IF NOT EXISTS source_records (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    external_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    title TEXT NOT NULL DEFAULT '',
    author TEXT NOT NULL DEFAULT '',
    isbn TEXT NOT NULL DEFAULT '',
    publisher TEXT NOT NULL DEFAULT '',
    publication_year INTEGER,
    price NUMERIC(12, 2),
    currency_id TEXT NOT NULL DEFAULT '',
    permalink TEXT NOT NULL DEFAULT '',
    thumbnail TEXT NOT NULL DEFAULT '',
    category_id TEXT NOT NULL DEFAULT '',
    search_term TEXT NOT NULL DEFAULT '',
    confidence_score NUMERIC(5, 4) NOT NULL DEFAULT 0,
    normalized_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_json JSONB NOT NULL,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_source_records_source_external_id UNIQUE (source, external_id),
    CONSTRAINT ck_source_records_status CHECK (status IN ('pending', 'approved', 'rejected', 'ignored')),
    CONSTRAINT ck_source_records_confidence_score CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

CREATE INDEX IF NOT EXISTS ix_source_records_source ON source_records (source);
CREATE INDEX IF NOT EXISTS ix_source_records_status ON source_records (status);
CREATE INDEX IF NOT EXISTS ix_source_records_search_term ON source_records (search_term);
CREATE INDEX IF NOT EXISTS ix_source_records_category_id ON source_records (category_id);
CREATE INDEX IF NOT EXISTS ix_source_records_last_seen_at ON source_records (last_seen_at DESC);
CREATE INDEX IF NOT EXISTS ix_source_records_raw_json_gin ON source_records USING GIN (raw_json);
