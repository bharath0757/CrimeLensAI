from app.core.database import driver
import logging

logger = logging.getLogger(__name__)

class Neo4jGraphService:
    @staticmethod
    async def upsert_entity(case_id: str, entity: dict):
        query = """
        MERGE (e:Entity {name: $name, type: $type})
        ON CREATE SET e.created_at = timestamp()
        SET e.updated_at = timestamp()
        
        MERGE (c:Case {id: $case_id})
        MERGE (c)-[:HAS_EVIDENCE]->(e)
        """
        async with driver.session() as session:
            await session.run(query, name=entity["name"].lower(), type=entity["entity_type"], case_id=case_id)

    @staticmethod
    async def create_relationship(case_id: str, rel: dict):
        query = f"""
        MATCH (src:Entity {{name: $src_name, type: $src_type}})
        MATCH (tgt:Entity {{name: $tgt_name, type: $tgt_type}})
        
        MERGE (src)-[r:{rel["relationship_type"]}]->(tgt)
        SET r.case_id = $case_id,
            r.timestamp = $timestamp,
            r.confidence_score = $confidence_score,
            r.description = $description
        RETURN r
        """
        async with driver.session() as session:
            await session.run(query, 
                src_name=rel["source_entity_name"].lower(), src_type=rel["source_entity_type"],
                tgt_name=rel["target_entity_name"].lower(), tgt_type=rel["target_entity_type"],
                case_id=case_id,
                timestamp=rel.get("properties", {}).get("timestamp"),
                confidence_score=rel.get("confidence_score", 1.0),
                description=rel.get("description", "")
            )

    @staticmethod
    async def get_linkage(case_id: str):
        query = """
        MATCH (c1:Case {id: $case_id})-[:HAS_EVIDENCE]->(e:Entity)<-[:HAS_EVIDENCE]-(c2:Case)
        WHERE c1 <> c2
        RETURN e.name AS shared_entity, e.type AS entity_type, c2.id AS linked_case_id
        """
        linked_cases = []
        async with driver.session() as session:
            result = await session.run(query, case_id=case_id)
            async for record in result:
                linked_cases.append({
                    "shared_entity": record["shared_entity"],
                    "entity_type": record["entity_type"],
                    "linked_case": record["linked_case_id"],
                    "why_linked": f"Both cases share {record['entity_type']} '{record['shared_entity']}'"
                })
        return {"case_id": case_id, "linked_cases": linked_cases}

    @staticmethod
    async def shortest_path(entity_a_name: str, entity_b_name: str):
        query = """
        MATCH (start:Entity {name: $start_name}), (end:Entity {name: $end_name})
        MATCH path = shortestPath((start)-[*]-(end))
        RETURN [n in nodes(path) | {name: n.name, type: n.type}] AS path_nodes,
               [r in relationships(path) | {type: type(r), case_id: r.case_id}] AS path_edges
        """
        async with driver.session() as session:
            result = await session.run(query, start_name=entity_a_name.lower(), end_name=entity_b_name.lower())
            record = await result.single()
            if not record:
                return {"entity_a": entity_a_name, "entity_b": entity_b_name, "path_found": False}
            
            return {
                "entity_a": entity_a_name,
                "entity_b": entity_b_name,
                "path_found": True,
                "path_nodes": record["path_nodes"],
                "path_edges": record["path_edges"],
                "explanation": f"Found shortest path with {len(record['path_edges'])} hops."
            }

    @staticmethod
    async def get_stats(case_id: str):
        query_nodes = "MATCH (c:Case {id: $case_id})-[:HAS_EVIDENCE]->(e:Entity) RETURN count(e) AS node_count"
        query_edges = """
        MATCH (c:Case {id: $case_id})-[:HAS_EVIDENCE]->(e1:Entity)
        MATCH (c)-[:HAS_EVIDENCE]->(e2:Entity)
        MATCH (e1)-[r]->(e2)
        WHERE r.case_id = $case_id
        RETURN count(r) AS edge_count
        """
        query_types = """
        MATCH (c:Case {id: $case_id})-[:HAS_EVIDENCE]->(e:Entity)
        RETURN e.type AS node_type, count(e) AS count
        """
        query_rel_types = """
        MATCH (c:Case {id: $case_id})-[:HAS_EVIDENCE]->(e1:Entity)
        MATCH (c)-[:HAS_EVIDENCE]->(e2:Entity)
        MATCH (e1)-[r]->(e2)
        WHERE r.case_id = $case_id
        RETURN type(r) AS rel_type, count(r) AS count
        """
        async with driver.session() as session:
            nodes_res = await session.run(query_nodes, case_id=case_id)
            node_count = (await nodes_res.single())["node_count"]
            
            edges_res = await session.run(query_edges, case_id=case_id)
            edge_count = (await edges_res.single())["edge_count"]
            
            types_res = await session.run(query_types, case_id=case_id)
            node_types = {rec["node_type"]: rec["count"] async for rec in types_res}
            
            rel_types_res = await session.run(query_rel_types, case_id=case_id)
            rel_types = {rec["rel_type"]: rec["count"] async for rec in rel_types_res}
            
            density = (2 * edge_count) / (node_count * (node_count - 1)) if node_count > 1 else 0.0
            
            return {
                "total_nodes": node_count,
                "total_edges": edge_count,
                "density": round(density, 4),
                "node_types_breakdown": node_types,
                "relationship_types_breakdown": rel_types
            }
            
    @staticmethod
    async def get_case_graph(case_id: str):
        query = """
        MATCH (c:Case {id: $case_id})-[:HAS_EVIDENCE]->(n:Entity)
        OPTIONAL MATCH (n)-[r]-(m:Entity)<-[:HAS_EVIDENCE]-(c)
        RETURN collect(DISTINCT n) AS nodes, collect(DISTINCT r) AS edges
        """
        async with driver.session() as session:
            result = await session.run(query, case_id=case_id)
            record = await result.single()
            if not record:
                return {"nodes": [], "edges": []}
            return {
                "nodes": [{"id": n.element_id, "name": n["name"], "type": n["type"]} for n in record["nodes"]],
                "edges": [{"source": r.start_node.element_id, "target": r.end_node.element_id, "type": type(r)} for r in record["edges"] if r is not None]
            }

    @staticmethod
    async def get_entity_connections(entity_id: str):
        query = """
        MATCH (e:Entity {name: $entity_name})-[r]-(m:Entity)
        RETURN collect(DISTINCT m) AS connected_nodes, collect(DISTINCT r) AS edges
        """
        async with driver.session() as session:
            result = await session.run(query, entity_name=entity_id.lower())
            record = await result.single()
            if not record:
                return {"connected_nodes": [], "edges": []}
            return {
                "connected_nodes": [{"id": n.element_id, "name": n["name"], "type": n["type"]} for n in record["connected_nodes"]],
                "edges": [{"source": r.start_node.element_id, "target": r.end_node.element_id, "type": type(r)} for r in record["edges"] if r is not None]
            }
