# CrimeLensAI — Graph Service

Owned by: Member 4 (Graph / Data Lead)

## Overview
Neo4j-backed graph analysis microservice for criminal network analysis.
Provides cross-case entity linkage, centrality analysis, community detection,
and shortest-path queries with human-readable explanations.

## Architecture
```
app/
  core/
    config.py         # Environment-based settings
    neo4j.py          # Neo4j driver lifecycle
  models/
    schemas.py        # Pydantic request/response models
  repositories/
    graph_repository.py  # Neo4j Cypher operations
  services/
    graph_service.py     # Entity/relationship business logic
    analytics_service.py # Centrality, communities, shortest path
  api/
    routes.py            # Thin API routes
  store.py               # In-memory graph and Neo4j sync orchestration
  analysis.py            # FIR analysis pipeline
  models.py              # Core data models
```

**Architecture Notes:**
- Neo4j is the canonical persistence layer when `GRAPH_BACKEND=neo4j`.
- A deterministic in-memory backend exists for testing and demo purposes without needing a Neo4j server.
- The `Store` orchestrates loading the graph from Neo4j into an in-memory snapshot upon startup.
- Current analytics (centrality, communities, shortest path) use portable **NetworkX** algorithms operating on the in-memory graph snapshot.
- We do not currently use Neo4j GDS for analytics. The current NetworkX implementation is a functional prototype.
- NLP integration is planned later and is not currently directly connected.


## Node Types
- (:Case {case_id}) — FIR case node
- (:Entity {id, entity_type, value, canonical_value, confidence}) — PERSON, PHONE, VEHICLE, UPI_ID, LOCATION, ORG
- (:LinkAlert {id, case_ids, severity, status, explanation}) — Cross-case alerts

## Relationships
- (:Case)-[:CONTAINS]->(:Entity) — Case-entity linkage with occurrence metadata
- (:Entity)-[:RELATED]->(:Entity) — Evidence-based entity relationships (USES, OWNS, CONTACTED, etc.)

## Environment Variables
| Variable | Default | Description |
|---|---|---|
| GRAPH_BACKEND | memory | Backend mode: `memory` or `neo4j` |
| NEO4J_URI | bolt://neo4j:7687 | Neo4j Bolt URI |
| NEO4J_USER | neo4j | Neo4j username |
| NEO4J_PASSWORD | neo4j_dev_password | Neo4j password |

## API Endpoints
| Method | Path | Description |
|---|---|---|
| GET | /health | Health check with Neo4j verification |
| POST | /api/v1/entities | Upsert entity node |
| POST | /api/v1/relationships | Create evidence-based relationship |
| GET | /api/v1/linkage/{case_id} | Cross-case linkage through shared entities |
| GET | /api/v1/centrality/{entity_id} | Degree, betweenness, PageRank centrality |
| GET | /api/v1/communities | Community detection (greedy modularity) |
| GET | /api/v1/shortest-path?entity_a=...&entity_b=... | Shortest path with narrative |
| GET | /api/v1/patterns/{case_id} | Explainable cross-case patterns |
| GET | /api/v1/link-predictions | Candidate missing links |
| GET | /api/v1/alerts | Officer-facing cross-case alerts |
| POST | /api/v1/alerts/{alert_id}/acknowledge | Acknowledge alert |
| POST | /api/v1/analyze/firs | End-to-end FIR analysis |

## Local Setup

### Without Docker
```bash
cd services/graph-service
pip install -r requirements.txt
GRAPH_BACKEND=memory uvicorn app.main:app --port 8002
```

### With Docker
```bash
docker compose up graph neo4j
```

## Neo4j Requirements
- Neo4j 5.x Community or Enterprise
- Constraints auto-created on startup
- (Note: Neo4j GDS is not currently used; analytics run via NetworkX)

## Running Tests
```bash
cd services/graph-service
python -m pytest tests/ -v
```

## Synthetic Example Graph
```
CASE-001: Rajesh Kumar, Phone +919876543210, Vehicle AP39AB1234, UPI rajesh@oksbi
CASE-002: Ramesh Kumar, Phone +919876543210, Vehicle KA01MG1234
CASE-003: Suresh Reddy, Vehicle AP39AB1234

Cross-case links:
  CASE-001 ↔ CASE-002: shared PHONE +919876543210
  CASE-001 ↔ CASE-003: shared VEHICLE AP39AB1234
```

## Example Entity Upsert Request
```json
{
  "case_id": "CASE-001",
  "entity_type": "PERSON",
  "value": "Rajesh Kumar",
  "normalized_value": "rajesh kumar",
  "confidence": 0.85
}
```

## Example Entity Upsert Response
```json
{
  "status": "created",
  "entity_id": "a1b2c3d4...",
  "entity_type": "PERSON",
  "canonical_value": "rajesh kumar",
  "created": true,
  "case_ids": ["CASE-001"],
  "explanation": "Entity PERSON 'Rajesh Kumar' created and linked to CASE-001."
}
```

## Example Linkage Response
```json
{
  "case_id": "CASE-001",
  "linked_cases": [
    {
      "case_id": "CASE-002",
      "shared_entities": [{"entity_id": "...", "entity_type": "PHONE", "value": "+919876543210", "canonical_value": "9876543210", "confidence": 0.99}],
      "link_strength": 0.63,
      "explanation": "CASE-001 and CASE-002 are linked because both reference PHONE +919876543210."
    }
  ]
}
```

## NLP Handoff Contract
The graph service accepts entities matching the NLP extraction output:
```json
{"case_id": "CASE-001", "entity_id": "cfd8eda1...", "entity_type": "PERSON", "value": "Rajesh Kumar", "normalized_value": "rajesh kumar", "confidence": 0.70}
```
Both `entity_id`/`id` and `normalized_value`/`canonical_value` field names are accepted.
