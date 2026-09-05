# Production completion evidence

Last verified: 2026-09-05. Branch: `codex/production-completion`.

CrimeLensAI is production-deployment ready at the repository level. The complete
investigator workflow runs from the built web application through FastAPI,
PostgreSQL, the extraction service, Neo4j, ingestion, and the append-only ledger.
All verification data is synthetic and must not be interpreted as an allegation.

## Final quality gates

- Frontend: 32 tests pass; TypeScript and the production Vite build pass.
- Case API: 118 tests pass with the PostgreSQL and live-ledger integration gates enabled.
- Entity extraction: 65 tests pass with the packaged spaCy model.
- Graph service: 76 tests pass.
- Ingestion service: 28 tests pass.
- Audit ledger: 28 tests pass with PostgreSQL concurrency, immutable-trigger,
  idempotency, batch, and privileged-tamper checks enabled.
- Ruff passes over `services/`, `scripts/`, and `database/`.
- Dataset validation passes with exactly 1,000 FIRs, 20,000 CDR rows, 20,000
  transactions, and four internally linked expected-pattern groups.
- The frontend was verified in an automated Chromium session at 1254 px width:
  login, dashboard, alert acknowledgement, Case Intake, structured evidence,
  Case Linkage, Network Analysis, Audit Trail, and live record verification all
  rendered without browser or console errors.

The test stack is `crimelens-final-e2e`. Only the built web application and API
are bound to loopback; PostgreSQL, Neo4j, extraction, graph, ingestion, and ledger
remain private to the container network. All containers are healthy.

## End-to-end evidence

- A new FIR was uploaded as a real text document, parsed by the extraction service,
  stored with source offsets in PostgreSQL, synchronized to Neo4j, linked to a
  second case using five scored signals, surfaced as an officer notification, and
  recorded in the verified ledger.
- Victim PII is masked in entity, graph, linkage, and PDF responses. Explicit
  unmasking is role-restricted and creates an attributed ledger event.
- CDR and transaction CSVs were validated, stored atomically, replay-deduplicated,
  synchronized as `CALLED`, `LOCATED_AT`, and `TRANSFERRED_TO` relationships, and
  verified after graph-service restart with exact INR 200.00 metadata.
- Neo4j contains and serves every required label: `PERSON`, `PHONE`, `VEHICLE`,
  `LOCATION`, `BANK`, `UPI`, and `CASE`; and every required relationship:
  `CALLED`, `TRANSFERRED_TO`, `OWNS`, `LOCATED_AT`, and `INVOLVED_IN`.
- A browser acknowledgement survived graph restart. Its request and completion
  events were delivered to the ledger and independently verified.
- Evidence PDF export returned HTTP 200, a matching SHA-256 response header, and
  an audit event ID. The five-page A4 report has no blank pages, contains the
  masking marker, excludes the victim name, and visually passed all-page review.

## Deployment readiness

- `render.yaml` provisions PostgreSQL, four private worker/services, and the public
  Case API with generated or dashboard-supplied secrets and a pre-deploy migration.
- `deployment/render/case-api.Dockerfile` builds successfully.
- The frontend production image uses Nginx SPA fallback and same-origin API proxying;
  `VITE_API_BASE_URL` remains the supported Vercel override.
- Every service has a secret-free `.env.example`; production validation rejects
  demo backends, short secrets, debug mode, wildcard CORS, and ledger auto-migration.
- GitHub Actions runs lint, datasets, frontend tests/build, all service tests,
  real PostgreSQL suites, and clean Compose workflow verification.

Actual Vercel and Render provisioning is intentionally not performed from this
local verification pass because it requires the owner's accounts, billing choices,
and production secret values. No source-code TODO or placeholder implementation
remains in the delivered workflow.
