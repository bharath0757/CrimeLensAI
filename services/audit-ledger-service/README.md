# Audit Ledger Service

Owned by Member 1 (Security & Audit Lead). Provides durable, tamper-evident audit
entries, retry-safe append, chain verification, and recursive field masking.
Officer login and JWT authorization belong to the case API; the obsolete duplicate
login/register stubs have been removed from this service.

## Configuration

Copy the service's `.env.example` to an ignored `.env`, then supply:

- `LEDGER_DATABASE_URL`: a PostgreSQL SQLAlchemy URL. SQLite is permitted only
  for local development/tests, not when `ENVIRONMENT=production`.
- `SERVICE_AUTH_TOKEN`: a randomly generated secret of at least 32 bytes, shared
  with trusted calling backends only. Never put it in a frontend/Vite variable.
- `ENVIRONMENT=production` for deployed instances.

Startup fails if configuration is incomplete or database initialization fails.
The service initializes `ledger_entries`, `ledger_head`, and append-only triggers.
Run migrations/initialization with a database owner; production runtime credentials
should have only the privileges needed for append, head update, and reads.
Separating initialization privileges from runtime privileges is a deployment gate
that still needs implementation in the repository's migration runner.

## API

All data endpoints require `X-Service-Token`. API documentation is at `/docs`;
OpenAPI is at `/api/v1/openapi.json`. Readiness is `/api/v1/health` (also `/health`).

| Endpoint | Meaning |
| --- | --- |
| `POST /api/v1/ledger/record` | Append a caller-generated UUID `event_id`, `record_id`, optional `case_id`, `actor`, `action`, `resource_type`, and JSON `payload`. |
| `GET /api/v1/ledger/chain` | Paginate immutable records; optional repeated `case_id` filters. Listing does not claim verification. |
| `GET /api/v1/ledger/verify/{record_id}` | Check a stored event ID or the latest event for an exact resource ID and verify the entire stored chain/head snapshot. Unknown or out-of-scope IDs return 404. |
| `POST /api/v1/privacy/mask` | Recursively redact named sensitive fields without modifying the input. This does not authorize unmasking. |

The case API derives case filters from authenticated officer access and strips raw
audit payloads from its list response. It does not let browser clients append
arbitrary actors or events. Unmask authorization and durable unmask audit events
remain part of the case API integration work.

## Integrity model

Version 1 hashes the UTF-8 representation of JSON sorted by key, without optional
whitespace, with non-ASCII characters preserved and non-finite numbers rejected.
The hash covers sequence, version, event ID, resource/case IDs, actor, action,
resource type, payload, UTC timestamp, and previous hash. The first previous hash
is 64 zeroes. Use the same serialization when independently verifying a checkpoint.

PostgreSQL transaction advisory locks serialize appends across processes. SQLite
uses database write transactions for tests. Repeating the same UUID and identical
event returns its existing entry; changing data under that UUID returns 409.
Database triggers reject ordinary update/delete operations (and PostgreSQL truncate).

Verification recomputes every chain link and compares the final sequence/hash with
the stored head. This detects modified data, gaps, predecessor changes, and tail
deletion while the head is intact. Preserve signed or independently retained
checkpoints/backups to detect a privileged rewrite of both the chain and its head.
The internal token authenticates a calling service; it does not protect against
that service itself being compromised and supplying false assertions.

This is a hash-chain ledger, not a consensus blockchain. A valid chain proves
consistency of stored audit events, not truth of evidence, current source-table
integrity, or legal admissibility. Comparing current records against recorded
snapshots must be implemented separately in the evidence workflow.

## Verification status

Tests cover persistence, concurrent independent writers, retry deduplication,
case filters, pagination, authentication, unknown IDs, field masking, mutation
triggers, and privileged tampering. Run `python -m pytest -q` from this service.
The container suite passes 26 tests across SQLite and an isolated PostgreSQL 16
database. PostgreSQL tests require `LEDGER_TEST_POSTGRES_URL` and refuse to use a
database not named `crimelens_verify`; each test creates/drops only its own schema.
The production image has also passed live health, unauthorized-access, append,
verification, and missing-record HTTP checks while running as UID 10001.
All-domain event delivery and full-stack deployment remain separate unfinished gates.

The Case API now delivers automatic mutation events through a PostgreSQL transactional
outbox (`database/migrations/001_audit_outbox.sql`). Row triggers capture users, cases,
documents, entities, relationships, CDR records and transactions, including cascaded
deletions. Events carry row-snapshot digests, authenticated actor context and request
IDs; raw evidence is not copied into the ledger payload. Leased claims and stable
event IDs make retries safe, including a lost HTTP acknowledgement after append.

Database-backed tests and live FIR workflows verify delivery and chain integrity.
Auditing non-row actions (login, reads, exports, unmasking), current-record comparison,
independent checkpoints and production database privilege separation remain unfinished.
