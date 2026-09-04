from fastapi import APIRouter
from app.services.neo4j_service import Neo4jGraphService
import logging

router = APIRouter(prefix="/api/v1", tags=["Graph"])

@router.post("/entities")
async def upsert_entity(payload: dict):
    case_id = payload.get("case_id")
    entity = payload.get("entity")
    await Neo4jGraphService.upsert_entity(case_id, entity)
    return {"status": "ok", "message": "Entity upserted in Neo4j"}

@router.post("/relationships")
async def create_relationship(payload: dict):
    case_id = payload.get("case_id")
    rel = payload.get("relationship")
    await Neo4jGraphService.create_relationship(case_id, rel)
    return {"status": "ok", "message": "Relationship created in Neo4j"}

@router.get("/linkage/{case_id}")
async def get_cross_case_linkage(case_id: str):
    return await Neo4jGraphService.get_linkage(case_id)

@router.get("/centrality/{entity_id}")
async def get_entity_centrality(entity_id: str):
    # BLOCKED: Centrality requires Graph Data Science projections which need dedicated graph setup
    # and memory mapping. Without a live dataset running GDS projections safely, we return blocked.
    return {
        "entity_id": entity_id,
        "centrality": {},
        "message": "BLOCKED: Neo4j GDS projection required for centrality."
    }

@router.get("/communities")
async def detect_communities():
    # BLOCKED: Community detection requires GDS Louvain algorithm.
    return {"communities": [], "message": "BLOCKED: Neo4j GDS projection required for communities."}

@router.get("/shortest-path")
async def shortest_path(entity_a: str, entity_b: str):
    return await Neo4jGraphService.shortest_path(entity_a, entity_b)

@router.get("/stats/{case_id}")
async def get_stats(case_id: str):
    return await Neo4jGraphService.get_stats(case_id)
