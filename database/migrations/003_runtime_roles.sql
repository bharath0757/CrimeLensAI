BEGIN;

INSERT INTO ledger_head(id,sequence,hash)
VALUES (1,0,repeat('0',64)) ON CONFLICT (id) DO NOTHING;

CREATE OR REPLACE FUNCTION ledger_reject_mutation() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'audit entries are append-only'; END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS ledger_append_only ON ledger_entries;
CREATE TRIGGER ledger_append_only BEFORE UPDATE OR DELETE OR TRUNCATE
ON ledger_entries FOR EACH STATEMENT EXECUTE FUNCTION ledger_reject_mutation();

CREATE OR REPLACE FUNCTION protect_ingestion_evidence() RETURNS trigger AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id OR NEW.case_id IS DISTINCT FROM OLD.case_id
       OR NEW.document_id IS DISTINCT FROM OLD.document_id OR NEW.kind IS DISTINCT FROM OLD.kind
       OR NEW.source_sha256 IS DISTINCT FROM OLD.source_sha256 OR NEW.source_text IS DISTINCT FROM OLD.source_text
       OR NEW.actor IS DISTINCT FROM OLD.actor OR NEW.record_count IS DISTINCT FROM OLD.record_count
       OR NEW.inserted_records IS DISTINCT FROM OLD.inserted_records
       OR NEW.duplicate_records IS DISTINCT FROM OLD.duplicate_records
       OR NEW.graph_operations IS DISTINCT FROM OLD.graph_operations OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'ingestion evidence and delivery instructions are immutable';
    END IF;
    IF NEW.graph_cursor < OLD.graph_cursor OR NEW.graph_cursor > jsonb_array_length(NEW.graph_operations) THEN
        RAISE EXCEPTION 'ingestion graph cursor cannot move backwards or exceed the operation count';
    END IF;
    IF OLD.status = 'COMPLETED' AND NEW.status IS DISTINCT FROM OLD.status THEN
        RAISE EXCEPTION 'completed ingestion cannot return to pending';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS protect_ingestion_evidence ON ingestion_batches;
CREATE TRIGGER protect_ingestion_evidence BEFORE UPDATE ON ingestion_batches
FOR EACH ROW EXECUTE FUNCTION protect_ingestion_evidence();

CREATE OR REPLACE FUNCTION reject_ingestion_truncate() RETURNS trigger AS $$
BEGIN RAISE EXCEPTION 'ingestion evidence cannot be truncated'; END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS ingestion_no_truncate ON ingestion_batches;
CREATE TRIGGER ingestion_no_truncate BEFORE TRUNCATE ON ingestion_batches
FOR EACH STATEMENT EXECUTE FUNCTION reject_ingestion_truncate();

DROP TRIGGER IF EXISTS outbox_no_truncate ON audit_outbox;
CREATE TRIGGER outbox_no_truncate BEFORE TRUNCATE ON audit_outbox
FOR EACH STATEMENT EXECUTE FUNCTION ledger_reject_mutation();

INSERT INTO schema_migrations(version) VALUES ('003_runtime_roles') ON CONFLICT DO NOTHING;
COMMIT;
