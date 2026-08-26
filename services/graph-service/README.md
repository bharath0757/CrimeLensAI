# Graph Service

Owned by: Member 4 (Graph / Data Lead)

The graph service connects normalized entities to their source cases, ranks
cross-case links, detects bridge entities and converging signals, proposes
missing links, and creates officer alerts when a newly ingested entity appears
in another case.

Every analytical response explains which source-backed entities or paths
caused the result. Predictions are explicitly labelled
`INVESTIGATIVE_LEAD_NOT_FACT`; they are prioritisation aids, not accusations.

## Runtime modes

- `GRAPH_BACKEND=memory` (default): deterministic local/demo mode.
- `GRAPH_BACKEND=neo4j`: persists nodes, relationships, source occurrences and
  alert state to Neo4j while retaining portable NetworkX analytics.

## Core endpoints

- `POST /api/v1/analyze/firs` - end-to-end raw FIR input to officer-ready
  extraction, linkage, pattern and alert report.
- `POST /api/v1/entities`
- `POST /api/v1/relationships`
- `GET /api/v1/linkage/{case_id}`
- `GET /api/v1/patterns/{case_id}`
- `GET /api/v1/link-predictions`
- `GET /api/v1/alerts`
- `POST /api/v1/alerts/{alert_id}/acknowledge`
- `GET /api/v1/centrality/{entity_id}`
- `GET /api/v1/communities`
- `GET /api/v1/shortest-path`
