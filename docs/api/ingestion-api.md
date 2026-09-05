# Ingestion API

The ingestion service validates structured evidence; the Case API remains the
public and durable write boundary.

- `POST /api/v1/validate` validates UTF-8 CSV text or JSON records for `cdr` or
  `transactions`, normalizes values, rejects duplicate/conflicting identifiers,
  and returns row-level source references.
- Legacy `/api/v1/ingest/fir`, `/cdr`, and `/transaction` adapters require the
  officer's bearer token and forward it to the Case API. They never mint an
  administrator identity.
- `GET /health` reports process readiness.

Accepted uploads are capped by the Case API, stored with SHA-256 provenance, and
delivered asynchronously to Neo4j using an idempotent batch identifier.
