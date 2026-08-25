# Infrastructure

This directory contains deployment-related configuration.

## Docker Compose (Local Development)

The primary Docker Compose file lives at the project root (`/docker-compose.yml`) for convenience. Run:

```bash
docker compose up --build
```

## Individual Service Deployment

Each service has its own `Dockerfile` and can be deployed independently to:
- **Render** — connect GitHub repo, set build context to the service directory
- **Railway** — similar to Render, supports monorepo deploy contexts
- **Fly.io** — use `fly launch` from within the service directory

### Deployment Checklist

1. Set environment variables on the hosting platform (see `.env.example`)
2. Ensure PostgreSQL and Neo4j are provisioned (most platforms offer managed add-ons)
3. Build and deploy each service independently using its Dockerfile
4. Update service URLs in environment config to point to deployed instances
5. Deploy the frontend as a static site (Vercel, Netlify, or similar)

## Database Initialization

PostgreSQL schema migrations are managed via Alembic (from the API service).
Neo4j schema constraints are applied on service startup by the graph service.
