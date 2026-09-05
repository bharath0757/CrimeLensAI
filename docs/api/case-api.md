# Case API

The Case API is the only public backend service. Interactive documentation is at
`/docs`; its machine-readable contract is `/api/v1/openapi.json`.

All `/api/v1/*` routes except login and health require a JWT bearer token. Case
access is restricted by assignment for investigators and analysts; supervisors
and administrators can access the wider operational view. The API orchestrates
PostgreSQL, extraction, Neo4j graph, ingestion validation, and the audit ledger.

Core route groups:

- `/api/v1/auth`: login and current identity.
- `/api/v1/cases`, `/documents`, `/entities`, `/relationships`: case evidence.
- `/api/v1/extraction`: FIR text/file previews with offsets and confidence.
- `/api/v1/cases/{case_id}/ingestion`: CDR and transaction uploads.
- `/api/v1/graph` and `/api/v1/dashboard`: link analysis, alerts, and metrics.
- `/api/v1/ledger`: chain browsing and record verification.
- `/api/v1/cases/{case_id}/evidence-report.pdf`: privacy-safe evidence report.

Errors use proper HTTP status codes and the standard body `{"detail": "..."}`.
The root `/health` endpoint includes dependency readiness and returns 503 when a
required production dependency is unavailable.
