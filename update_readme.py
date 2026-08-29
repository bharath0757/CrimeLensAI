with open('services/graph-service/README.md', 'r') as f:
    content = f.read()

import re

# Architecture block
arch_pattern = r'## Architecture.*?```.*?```'
new_arch = '''## Architecture
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
'''
content = re.sub(arch_pattern, new_arch, content, flags=re.DOTALL)

# Neo4j Requirements block
req_pattern = r'## Neo4j Requirements.*?## Running Tests'
new_req = '''## Neo4j Requirements
- Neo4j 5.x Community or Enterprise
- Constraints auto-created on startup
- (Note: Neo4j GDS is not currently used; analytics run via NetworkX)

## Running Tests'''
content = re.sub(req_pattern, new_req, content, flags=re.DOTALL)

with open('services/graph-service/README.md', 'w') as f:
    f.write(content)
