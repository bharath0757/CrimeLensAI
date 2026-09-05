CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('ADMIN', 'INVESTIGATOR', 'ANALYST')),
    badge_number TEXT,
    agency TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    case_number TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    complaint TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'IN_PROGRESS', 'CLOSED', 'ARCHIVED')),
    priority TEXT NOT NULL DEFAULT 'MEDIUM' CHECK (priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')),
    owner_id TEXT NOT NULL REFERENCES users(id),
    assigned_investigator_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    tags JSONB NOT NULL DEFAULT '[]'::jsonb,
    location TEXT,
    incident_date DATE,
    document_count INTEGER NOT NULL DEFAULT 0 CHECK (document_count >= 0),
    entity_count INTEGER NOT NULL DEFAULT 0 CHECK (entity_count >= 0),
    relationship_count INTEGER NOT NULL DEFAULT 0 CHECK (relationship_count >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS documents (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    file_type TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL CHECK (file_size_bytes >= 0),
    file_path TEXT,
    processing_status TEXT NOT NULL DEFAULT 'PENDING',
    extracted_entity_count INTEGER NOT NULL DEFAULT 0,
    extracted_relationship_count INTEGER NOT NULL DEFAULT 0,
    uploaded_by TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS entities (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    description TEXT,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (confidence_score BETWEEN 0 AND 1),
    source_document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    review_status TEXT NOT NULL DEFAULT 'PENDING' CHECK (review_status IN ('PENDING', 'CONFIRMED', 'REJECTED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (case_id, entity_type, normalized_value)
);

CREATE TABLE IF NOT EXISTS relationships (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    source_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    target_entity_id TEXT NOT NULL REFERENCES entities(id) ON DELETE CASCADE,
    relationship_type TEXT NOT NULL,
    description TEXT,
    properties JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence_score DOUBLE PRECISION NOT NULL DEFAULT 1.0 CHECK (confidence_score BETWEEN 0 AND 1),
    source_document_id TEXT REFERENCES documents(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS cdr_records (
    cdr_id TEXT NOT NULL,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    caller TEXT NOT NULL,
    receiver TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    duration_seconds INTEGER NOT NULL CHECK (duration_seconds >= 0),
    tower TEXT NOT NULL,
    imei TEXT NOT NULL,
    PRIMARY KEY (case_id, cdr_id)
);

CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT NOT NULL,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    amount NUMERIC(14,2) NOT NULL CHECK (amount > 0),
    upi_id TEXT NOT NULL,
    occurred_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (case_id, transaction_id)
);

CREATE TABLE IF NOT EXISTS ledger_entries (
    sequence INTEGER PRIMARY KEY,
    id VARCHAR(36) NOT NULL UNIQUE,
    version INTEGER NOT NULL,
    record_id TEXT NOT NULL,
    case_id TEXT,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    payload TEXT NOT NULL,
    timestamp VARCHAR(40) NOT NULL,
    previous_hash VARCHAR(64) NOT NULL,
    hash VARCHAR(64) NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ledger_head (
    id INTEGER PRIMARY KEY,
    sequence INTEGER NOT NULL,
    hash VARCHAR(64) NOT NULL
);

CREATE INDEX IF NOT EXISTS cases_search_idx ON cases USING GIN (
    to_tsvector('english', coalesce(title, '') || ' ' || coalesce(description, '') || ' ' || coalesce(complaint, ''))
);
CREATE INDEX IF NOT EXISTS entities_case_idx ON entities(case_id);
CREATE INDEX IF NOT EXISTS entities_normalized_idx ON entities(entity_type, normalized_value);
CREATE INDEX IF NOT EXISTS relationships_case_idx ON relationships(case_id);
CREATE INDEX IF NOT EXISTS relationships_nodes_idx ON relationships(source_entity_id, target_entity_id);
CREATE INDEX IF NOT EXISTS cdr_case_idx ON cdr_records(case_id);
CREATE INDEX IF NOT EXISTS cdr_phone_idx ON cdr_records(caller, receiver);
CREATE INDEX IF NOT EXISTS transactions_case_idx ON transactions(case_id);
CREATE INDEX IF NOT EXISTS transactions_accounts_idx ON transactions(sender, receiver);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_record_id ON ledger_entries(record_id);
CREATE INDEX IF NOT EXISTS ix_ledger_entries_case_id ON ledger_entries(case_id);
