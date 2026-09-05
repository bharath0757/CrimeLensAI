# Audit Ledger API

This is an internal service. Every route under `/api/v1/ledger` requires the
shared `X-Service-Token` header.

- `POST /api/v1/ledger/record` appends one canonical event using an idempotent
  event ID. The row stores its own SHA-256 hash and the preceding row's hash.
- `GET /api/v1/ledger/chain` lists the append-only chain with optional case
  filtering and pagination.
- `GET /api/v1/ledger/verify/{record_id}` recomputes the selected record and its
  chain ancestry; it never reports success when storage is unavailable.
- `GET /api/v1/health` verifies durable storage connectivity.

PostgreSQL triggers reject ledger mutation or deletion. The service uses the
`crimelens_ledger` role, which can append entries and advance the serialized
ledger head but cannot modify case data.
