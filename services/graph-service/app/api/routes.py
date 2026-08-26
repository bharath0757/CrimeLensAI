"""
Graph Service — API Routes
============================
Endpoints for Neo4j-backed graph queries and analysis.
"""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Graph"])


@router.post("/entities")
async def upsert_entity(payload: dict):
    """
    Create or update an entity node in the graph.

    Entity types: PERSON, PHONE, VEHICLE, UPI_ID, LOCATION, ORG
    Each node is linked to its source case(s).

    TODO: Implement Neo4j MERGE with case linkage
    """
    return {"status": "ok", "message": "Entity upsert placeholder"}


@router.post("/relationships")
async def create_relationship(payload: dict):
    """
    Create a relationship between two entity nodes.

    Every relationship includes:
    - relationship_type (e.g., CONTACTED, TRANSACTED, CO_LOCATED)
    - source_case_id: the case that evidences this relationship
    - confidence: extraction confidence score
    - why_linked: human-readable explanation

    TODO: Implement Cypher CREATE/MERGE for relationships
    """
    return {"status": "ok", "message": "Relationship creation placeholder"}


@router.get("/linkage/{case_id}")
async def get_cross_case_linkage(case_id: str):
    """
    Find all cases linked to the given case through shared entities.

    Returns a subgraph of connected cases with:
    - The shared entity (name, type)
    - The linking path
    - A human-readable "why linked" explanation

    TODO: Implement Cypher traversal query
    """
    return {
        "case_id": case_id,
        "linked_cases": [],
        "message": "Cross-case linkage placeholder",
    }


@router.get("/centrality/{entity_id}")
async def get_entity_centrality(entity_id: str):
    """
    Compute centrality metrics for an entity node.

    Returns degree, betweenness, and PageRank centrality to identify
    key nodes (e.g., a phone number that appears in 15 cases).

    TODO: Implement Neo4j GDS centrality algorithms
    """
    return {
        "entity_id": entity_id,
        "centrality": {},
        "message": "Centrality analysis placeholder",
    }


@router.get("/communities")
async def detect_communities():
    """
    Run community detection on the entity graph.

    Groups entities into clusters that likely represent the same
    criminal network or operation.

    TODO: Implement Louvain / Label Propagation via Neo4j GDS
    """
    return {"communities": [], "message": "Community detection placeholder"}


@router.get("/shortest-path")
async def shortest_path(entity_a: str, entity_b: str):
    """
    Find the shortest path between two entities in the graph.

    Returns the path with all intermediate nodes and relationships,
    plus a human-readable narrative explaining the connection.

    TODO: Implement Cypher shortestPath query
    """
    return {
        "entity_a": entity_a,
        "entity_b": entity_b,
        "path": [],
        "explanation": "Shortest path placeholder",
    }
