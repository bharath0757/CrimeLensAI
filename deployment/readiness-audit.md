# Deployment readiness audit — 2026-09-06

Status: repository fixes verified locally; **production deployment is not verified**.
The current task's Vercel account lookup returns `Unknown tool`, and Render tools
are not available. No platform settings, secrets, or deployments were changed.

## Repository findings

| Area | Inspected configuration and release requirement |
| --- | --- |
| Frontend | `frontend/`: React 19, TypeScript 6, Vite 8; npm with `package-lock.json`. Node 24 matches CI and Docker. |
| Frontend build | Root directory `frontend`; install `npm ci`; build `npm run build`; output `dist`. Vercel serves the static output, not the development server. |
| Frontend routing | `BrowserRouter`; `frontend/vercel.json` rewrites deep links to `index.html`. Verify refresh on `/cases/new` and `/case-linkage` after deployment. |
| Backend | FastAPI/Python 3.11 in `services/case-api/`; separate extraction, graph, ledger, and ingestion services under `services/`. pip requirements per service. |
| Render API build | Repository-root Docker context and `deployment/render/case-api.Dockerfile`. Do not configure `services/case-api` as the root for this Dockerfile. |
| Render start | Docker CMD runs `python /bootstrap/bootstrap.py` followed by Uvicorn on `0.0.0.0:$PORT` (fallback 10000). Keep the image's start command. |
| Other services | Four private Docker services, with their service directories as build contexts. Internal host/port references are normalized by application configuration. |
| PostgreSQL | Render Blueprint defines PostgreSQL 16; bootstrap uses owner `MIGRATION_DATABASE_URL`, applies schema/migrations, provisions runtime roles and administrator. Runtime API/ledger URLs derive from their separate role passwords. |
| Migration entrypoint | `/bootstrap/bootstrap.py` is the production entrypoint. The separate repository helper `services/case-api/migrate.py` is not a replacement for role/admin bootstrap in the Render image. |
| Neo4j | Graph service requires an existing reachable Neo4j instance. Blueprint does not provision it. Actual production connectivity is unverified. |
| API communication | Frontend adds `/api/v1` itself. `VITE_API_BASE_URL` must contain only the public backend origin. The deployment guide previously duplicated the prefix; corrected. |
| CORS | Explicit origin allowlist. Added exposure of PDF filename, report SHA-256, and audit event ID headers for the cross-origin Vercel frontend. No wildcard origin added. |
| Authentication | JWT bearer authentication with issuer/audience/expiry and active-user checks; account provisioning is administrator-only. Production requires explicit strong signing/service secrets and PostgreSQL. Live login remains unverified. |
| Localhost/development | Localhost defaults remain for local development and tests. Vercel build now rejects missing, HTTP, localhost, credential-bearing, or path-bearing API origins. Docker's same-origin proxy remains supported. Production must explicitly configure `ALLOWED_ORIGINS`. |
| Secrets | Tracked environment files are examples. No obvious private-key/common token signatures found in the targeted scan; this is not an exhaustive secret-history certification. Do not commit real `.env` files or use demo credentials in production. |
| Storage | API needs its `/data` persistent disk for uploads. Validate writable access after deployment. Review existing resources and plan costs before creating a new Blueprint. |
| Health | `/health` verifies database access and API delivery workers. It does not prove downstream service availability or the complete investigator workflow. |
| Dependency verification | Existing local npm dependencies and cached Python test image used for this pass. A fresh platform build and production runtime checks are still required. |

## Environment variable names

Vercel application variable: `VITE_API_BASE_URL` (Production and any Preview
environment used for integration tests). Never place backend secrets in `VITE_*`.

Render prompted inputs: `BOOTSTRAP_ADMIN_EMAIL`, `BOOTSTRAP_ADMIN_PASSWORD`,
`ALLOWED_ORIGINS`, `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`.

Render generated/shared secrets: `SECRET_KEY`, `SERVICE_AUTH_TOKEN`,
`API_DATABASE_PASSWORD`, `LEDGER_DATABASE_PASSWORD`.

Render resource references: `MIGRATION_DATABASE_URL`, `AI_SERVICE_URL`,
`GRAPH_SERVICE_URL`, `LEDGER_SERVICE_URL`, `INGESTION_SERVICE_URL`,
`EXTRACTION_SERVICE_URL`, `API_SERVICE_URL`.

Render settings already specified in the Blueprint: `ENVIRONMENT`, `DEBUG`,
`DATA_BACKEND`, `GRAPH_BACKEND`, `LEDGER_AUTO_MIGRATE`,
`SCHEMA_WAIT_TIMEOUT_SECONDS`, `SEED_SYNTHETIC`, `ALLOW_DEMO_SEED`, `UPLOAD_DIR`.
Render supplies `PORT`. API and ledger derive `DATABASE_URL` from the migration
URL and their role passwords when it is not explicitly supplied.

Actual account values have not been accessed or invented. Confirm the selected
deployment branch contains these fixes; the working branch is
`codex/production-completion`, not necessarily the platforms' default branch.

## Verification in this pass

- Frontend: 49 tests passed; TypeScript and production build passed.
- Vercel-mode build passed with a non-secret test HTTPS origin; no deployment
  was made using that test origin.
- API: 101 tests passed, 20 skipped because an isolated integration database
  was not supplied. Two dependency deprecation warnings remain.
- Python repository lint passed after correcting one extra blank line in the
  teammate's migration helper. No migration behavior was changed.

## Production release gate

1. Establish callable platform access; inspect existing projects, resources,
   branches, plans, environment-variable presence, and recent deployment logs.
2. Configure the real secrets securely and an exact Vercel origin allowlist.
3. Deploy Render; confirm bootstrap completion, migrations, runtime roles,
   writable uploads, and all five services. Confirm Neo4j connectivity.
4. Build Vercel from the correct root with the actual Render API origin.
5. Verify authentication, unauthorized access rejection, FIR upload/extraction,
   PostgreSQL persistence, graph creation, related-case explanation, alerts,
   dashboard metrics, structured ingestion, audit verification, and PDF export.
6. Verify report metadata headers from the browser, route refreshes, allowed and
   rejected CORS origins, runtime error logs, and a clean platform build.

Do not mark this release production-ready until these live checks pass.
