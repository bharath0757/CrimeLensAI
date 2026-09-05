# Local setup

1. Install Docker Desktop with Compose v2.
2. Copy `.env.example` to `.env` and set every blank secret. Database-role and
   service tokens must contain at least 32 bytes; the bootstrap password must be
   12–72 UTF-8 bytes.
3. Run `docker compose up --build --wait` from the repository root.
4. Open `http://localhost:5173` and sign in with the configured bootstrap
   administrator. API documentation is at `http://localhost:8000/docs`.

Only the UI and Case API bind host ports. PostgreSQL, Neo4j, and internal services
are intentionally reachable only from the Compose network.

For a reproducible judge dataset, set both synthetic switches in `.env`. To reset
that local demo, stop the explicitly named Compose project with volumes and start
it again. Never point verification scripts at operational evidence databases.
