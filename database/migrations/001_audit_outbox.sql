BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_outbox (
    sequence BIGSERIAL PRIMARY KEY,
    event_id UUID NOT NULL UNIQUE,
    event JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    claim_token UUID,
    claimed_until TIMESTAMPTZ,
    delivered_at TIMESTAMPTZ,
    ledger_hash VARCHAR(64),
    last_error TEXT
);
CREATE INDEX IF NOT EXISTS audit_outbox_pending_idx
    ON audit_outbox(next_attempt_at, sequence) WHERE delivered_at IS NULL;

CREATE OR REPLACE FUNCTION capture_domain_audit() RETURNS trigger AS $$
DECLARE
    snapshot JSONB;
    prior_snapshot JSONB;
    event_uuid UUID := gen_random_uuid();
    resource TEXT;
    resource_id TEXT;
    associated_case TEXT;
    snapshot_digest TEXT;
    prior_digest TEXT;
BEGIN
    IF TG_OP = 'UPDATE' AND NEW IS NOT DISTINCT FROM OLD THEN
        RETURN NEW;
    END IF;
    snapshot := CASE WHEN TG_OP = 'DELETE' THEN to_jsonb(OLD) ELSE to_jsonb(NEW) END;
    prior_snapshot := CASE WHEN TG_OP IN ('UPDATE', 'DELETE') THEN to_jsonb(OLD) ELSE NULL END;
    resource := CASE TG_TABLE_NAME
        WHEN 'cases' THEN 'CASE' WHEN 'entities' THEN 'ENTITY'
        WHEN 'relationships' THEN 'RELATIONSHIP' WHEN 'documents' THEN 'DOCUMENT'
        WHEN 'users' THEN 'USER' WHEN 'cdr_records' THEN 'CDR'
        WHEN 'transactions' THEN 'TRANSACTION'
        WHEN 'ingestion_batches' THEN 'INGESTION_BATCH' END;
    IF resource IS NULL THEN
        RAISE EXCEPTION 'Audit resource mapping missing for table %', TG_TABLE_NAME;
    END IF;
    resource_id := coalesce(snapshot->>'id', snapshot->>'cdr_id', snapshot->>'transaction_id');
    associated_case := CASE WHEN TG_TABLE_NAME = 'cases' THEN resource_id ELSE snapshot->>'case_id' END;
    snapshot_digest := encode(public.digest(convert_to(snapshot::text, 'UTF8'), 'sha256'), 'hex');
    IF prior_snapshot IS NOT NULL THEN
        prior_digest := encode(public.digest(convert_to(prior_snapshot::text, 'UTF8'), 'sha256'), 'hex');
    END IF;
    INSERT INTO audit_outbox(event_id, event) VALUES (
        event_uuid,
        jsonb_build_object(
            'event_id', event_uuid::text,
            'record_id', resource_id,
            'case_id', associated_case,
            'actor', coalesce(nullif(current_setting('crimelens.actor', true), ''), 'database:' || session_user),
            'action', resource || '_' || TG_OP,
            'resource_type', resource,
            'payload', jsonb_build_object(
                'snapshot_hash', snapshot_digest,
                'previous_snapshot_hash', prior_digest,
                'hash_format', 'postgres-jsonb-text-v1',
                'operation', TG_OP,
                'occurred_at', clock_timestamp(),
                'request_id', nullif(current_setting('crimelens.request_id', true), ''),
                'database_transaction_id', txid_current()::text
            )
        )
    );
    IF TG_OP = 'DELETE' THEN RETURN OLD; END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE table_name TEXT;
BEGIN
    FOREACH table_name IN ARRAY ARRAY['users','cases','documents','entities','relationships','cdr_records','transactions'] LOOP
        IF NOT EXISTS (
            SELECT 1 FROM pg_trigger WHERE tgname = 'capture_domain_audit'
            AND tgrelid = to_regclass(table_name)
        ) THEN
            EXECUTE format('CREATE TRIGGER capture_domain_audit AFTER INSERT OR UPDATE OR DELETE ON %I '
                           'FOR EACH ROW EXECUTE FUNCTION capture_domain_audit()', table_name);
        END IF;
    END LOOP;
END;
$$;

CREATE OR REPLACE FUNCTION protect_outbox_event() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN RAISE EXCEPTION 'audit outbox records cannot be deleted'; END IF;
    IF NEW.event_id IS DISTINCT FROM OLD.event_id OR NEW.event IS DISTINCT FROM OLD.event
       OR NEW.sequence IS DISTINCT FROM OLD.sequence OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'audit outbox event content is immutable';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$ BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname='protect_outbox_event' AND tgrelid='audit_outbox'::regclass) THEN
        CREATE TRIGGER protect_outbox_event BEFORE UPDATE OR DELETE ON audit_outbox
            FOR EACH ROW EXECUTE FUNCTION protect_outbox_event();
    END IF;
END; $$;

INSERT INTO schema_migrations(version) VALUES ('001_audit_outbox') ON CONFLICT DO NOTHING;
COMMIT;
