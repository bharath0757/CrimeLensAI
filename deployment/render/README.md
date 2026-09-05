# Render backend deployment

`render.yaml` provisions PostgreSQL, the public Case API, and private extraction,
graph, ledger, and ingestion services in the Singapore region. The graph service
uses an external Neo4j deployment (Neo4j Aura is suitable) supplied through the
three prompted `NEO4J_*` secrets.

## Blueprint inputs

Render prompts for these values on the first Blueprint creation:

- `BOOTSTRAP_ADMIN_EMAIL`: the first administrator's email.
- `BOOTSTRAP_ADMIN_PASSWORD`: 12–72 UTF-8 bytes; use a unique password.
- `ALLOWED_ORIGINS`: a JSON list containing the deployed Vercel origin, for
  example `["https://crimelens.example"]`.
- `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`: the production Neo4j Bolt
  credentials. Use an encrypted `neo4j+s://` URI when the provider supports it.

The Blueprint generates the JWT, service-to-service, API database-role, and
ledger database-role secrets. On paid Render services, the Case API pre-deploy
command applies migrations before release. The Docker start command repeats the
same idempotent bootstrap before starting Uvicorn, so first deployment also
works on plans that do not support pre-deploy commands and when the service was
created manually. The ledger waits for all three migration versions and its
least-privileged database role before starting. Synthetic demo data is
deliberately disabled in production.

The migration process needs `MIGRATION_DATABASE_URL` from the Render PostgreSQL
`connectionString`. Do not replace it with the API runtime-role URL. Successful
logs include `Schema migrations and deployment bootstrap completed
successfully`; the API must not be marked healthy before that message appears.

## Vercel frontend

Deploy `frontend/` as the Vercel project root. Set
`VITE_API_BASE_URL=https://<crimelens-api-host>/api/v1` for Production and Preview.
The committed `frontend/vercel.json` provides the SPA rewrite required by
`BrowserRouter`.

## Release checks

1. Require CI checks before merging the deployment branch.
2. Confirm all five Render services report healthy and `/health` on the Case API
   reports PostgreSQL, extraction, graph, ledger, and ingestion as healthy.
3. Log in with the bootstrap administrator, create a permanent named officer
   account, and rotate the bootstrap password.
4. Upload a test FIR and verify extraction, linkage, alert, audit verification,
   and PDF export before enabling the Vercel production domain.
