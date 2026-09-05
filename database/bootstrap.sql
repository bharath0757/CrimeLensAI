\set ON_ERROR_STOP on
\ir schema.sql
\ir migrations/001_audit_outbox.sql
\ir migrations/002_structured_ingestion.sql
\ir migrations/003_runtime_roles.sql
\if :{?seed_synthetic}
\else
\set seed_synthetic false
\endif
\if :seed_synthetic
\ir seed.sql
\endif
