BEGIN;

-- Evidence identifiers can legitimately occur in multiple investigations.
-- Keep the source identifier intact, with case-scoped uniqueness.
ALTER TABLE cdr_records DROP CONSTRAINT IF EXISTS cdr_records_pkey;
ALTER TABLE cdr_records ADD PRIMARY KEY (case_id, cdr_id);
ALTER TABLE transactions DROP CONSTRAINT IF EXISTS transactions_pkey;
ALTER TABLE transactions ADD PRIMARY KEY (case_id, transaction_id);

CREATE TABLE IF NOT EXISTS ingestion_batches (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(id) ON DELETE CASCADE,
    document_id TEXT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    kind TEXT NOT NULL CHECK (kind IN ('cdr','transactions')),
    source_sha256 TEXT NOT NULL CHECK (length(source_sha256)=64),
    source_text TEXT NOT NULL,
    actor TEXT NOT NULL,
    record_count INTEGER NOT NULL CHECK (record_count > 0),
    inserted_records INTEGER NOT NULL CHECK (inserted_records >= 0),
    duplicate_records INTEGER NOT NULL CHECK (duplicate_records >= 0),
    graph_operations JSONB NOT NULL,
    graph_cursor INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'PENDING' CHECK (status IN ('PENDING','COMPLETED')),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claim_token UUID,
    claimed_until TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    UNIQUE(case_id,kind,source_sha256)
);
CREATE INDEX IF NOT EXISTS ingestion_pending_idx ON ingestion_batches(next_attempt_at) WHERE status='PENDING';
DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='capture_domain_audit' AND tgrelid='ingestion_batches'::regclass) THEN
        CREATE TRIGGER capture_domain_audit AFTER INSERT OR DELETE ON ingestion_batches
            FOR EACH ROW EXECUTE FUNCTION capture_domain_audit();
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='capture_ingestion_status' AND tgrelid='ingestion_batches'::regclass) THEN
        CREATE TRIGGER capture_ingestion_status AFTER UPDATE OF status ON ingestion_batches
            FOR EACH ROW WHEN (OLD.status IS DISTINCT FROM NEW.status) EXECUTE FUNCTION capture_domain_audit();
    END IF;
END; $$;
INSERT INTO schema_migrations(version) VALUES ('002_structured_ingestion') ON CONFLICT DO NOTHING;
COMMIT;
