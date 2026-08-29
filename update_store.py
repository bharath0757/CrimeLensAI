import re

with open('services/graph-service/app/store.py', 'r') as f:
    content = f.read()

# 1. Update upsert_entity to prefer payload.id
upsert_entity_replacement = '''
            entity_id = payload.id
            if not entity_id:
                entity_id = self.canonical_index.get(key) or str(
                    uuid.uuid5(uuid.NAMESPACE_URL, f"crimelens:entity:{entity_type}:{canonical}")
                )
'''
# I'll replace the block that calculates entity_id in InMemoryGraphStore.upsert_entity
content = re.sub(
    r'            entity_id = self\.canonical_index\.get\(key\).*?\)\n',
    upsert_entity_replacement.lstrip('\n'),
    content,
    flags=re.DOTALL
)


# 2. Update Neo4jGraphStore
neo4j_graph_store_replacement = '''class Neo4jGraphStore(InMemoryGraphStore):
    """Neo4j persistence with portable in-process analytics."""

    def __init__(self) -> None:
        super().__init__()
        self.repo = None

    def hydrate(self) -> None:
        from app.core.neo4j import neo4j_manager
        from app.repositories.graph_repository import GraphRepository
        
        self.repo = GraphRepository(neo4j_manager.driver)
        
        with neo4j_manager.get_session() as session:
            rows = session.run(
                "MATCH (c:Case)-[o:HAS_ENTITY]->(e:Entity) RETURN c.case_id AS case_id, e, properties(o) AS occurrence"
            )
            for row in rows:
                data = dict(row["e"])
                entity_id = data["id"]
                entity = self.entities.setdefault(entity_id, {**data, "occurrences": []})
                entity["occurrences"].append({"case_id": row["case_id"], **row["occurrence"]})
                self.canonical_index[(data["entity_type"], data["canonical_value"])] = entity_id
                self.case_entities[row["case_id"]].add(entity_id)
            rows = session.run(
                "MATCH (a:Entity)-[r:RELATED]->(b:Entity) RETURN a.id AS source, b.id AS target, properties(r) AS relation"
            )
            for row in rows:
                relation = dict(row["relation"])
                relation.update(source_entity_id=row["source"], target_entity_id=row["target"])
                self.relationships[relation["id"]] = relation
            rows = session.run("MATCH (a:LinkAlert) RETURN properties(a) AS alert")
            for row in rows:
                alert = dict(row["alert"])
                alert["case_ids"] = list(alert.get("case_ids", []))
                alert["shared_entity_ids"] = list(alert.get("shared_entity_ids", []))
                self.alerts[alert["id"]] = alert

    def upsert_entity(self, payload: EntityInput) -> dict[str, Any]:
        result = super().upsert_entity(payload)
        self._persist_entity(result["entity"], payload.case_id)
        return result

    def _persist_entity(self, entity: dict[str, Any], case_id: str) -> None:
        if not self.repo:
            return
        occurrence = next((item for item in reversed(entity["occurrences"]) if item["case_id"] == case_id), {})
        self.repo.upsert_entity(
            entity_id=entity["id"],
            entity_type=entity["entity_type"],
            value=entity["value"],
            canonical_value=entity["canonical_value"],
            confidence=entity["confidence"],
            case_id=case_id,
            source_field=occurrence.get("source_field", "unknown"),
            start_offset=occurrence.get("start_offset", 0),
            end_offset=occurrence.get("end_offset", 0)
        )

    def _persist_relationship(self, relation: dict[str, Any]) -> None:
        if not self.repo:
            return
        self.repo.create_relationship(
            source_entity_id=relation["source_entity_id"],
            target_entity_id=relation["target_entity_id"],
            relationship_type=relation.get("relationship_type", "RELATED"),
            source_case_id=relation.get("source_case_id", ""),
            confidence=relation.get("confidence", 1.0),
            why_linked=relation.get("why_linked", ""),
            relationship_id=relation["id"],
            evidence_record_id=relation.get("evidence_record_id")
        )

    def _persist_alert(self, alert: dict[str, Any]) -> None:
        if not self.repo:
            return
        with self.repo._driver.session() as session:
            session.run("MERGE (a:LinkAlert {id:$id}) SET a += $properties", id=alert["id"], properties=alert)


def build_store() -> InMemoryGraphStore:
    import os
    if os.getenv("GRAPH_BACKEND", "memory").lower() != "neo4j":
        return InMemoryGraphStore()
    return Neo4jGraphStore()'''

content = re.sub(
    r'class Neo4jGraphStore\(InMemoryGraphStore\):.*def build_store\(\) -> InMemoryGraphStore:.*$',
    neo4j_graph_store_replacement,
    content,
    flags=re.DOTALL | re.MULTILINE
)

with open('services/graph-service/app/store.py', 'w') as f:
    f.write(content)
