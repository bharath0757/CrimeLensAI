# Graph API Documentation

The graph API is designed around explainability and officer action:

- `POST /api/v1/analyze/firs` accepts up to 100 raw FIR narratives, invokes
  batch entity extraction, updates the graph, and returns alerts, ranked links,
  patterns, source-backed case results and an officer action brief.
- `POST /api/v1/entities` upserts a canonical entity, links its source case,
  and creates an alert if the same entity exists in another case.
- `GET /api/v1/linkage/{case_id}` returns ranked linked cases plus a renderable
  subgraph and plain-language evidence explanation.
- `GET /api/v1/patterns/{case_id}` returns repeated identifiers,
  multi-signal convergence and bridge entities.
- `GET /api/v1/link-predictions` uses Jaccard and Adamic-Adar common-neighbour
  evidence to rank possible missing links.
- `GET /api/v1/alerts` and `POST /api/v1/alerts/{id}/acknowledge` implement the
  officer review queue.
- Centrality, communities and shortest-path endpoints provide network analysis.

Every predicted pattern is labelled `INVESTIGATIVE_LEAD_NOT_FACT`. Confidence
scores prioritise review; they never replace verification of original records.
