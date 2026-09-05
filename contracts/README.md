# CrimeLensAI API contracts

This directory records cross-team contract snapshots for the Case, extraction,
graph, ledger, and ingestion APIs. Runtime FastAPI schemas are authoritative and
available from each service at `/api/v1/openapi.json` (or `/openapi.json` for
internal services that do not override the default path).

- `openapi/` describes the externally consumed routes and payloads.
- `python/` contains portable Pydantic domain types for offline tooling.
- `typescript/` contains portable interfaces for consumers outside the React app.

The running frontend uses the narrower, UI-specific contracts in
`frontend/src/lib/contracts.ts`. A contract change must update its Pydantic model,
endpoint test, frontend type when applicable, and this snapshot in the same pull
request.
