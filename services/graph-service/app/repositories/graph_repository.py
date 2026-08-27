from __future__ import annotations

class GraphRepository:
    def __init__(self, driver):
        self._driver = driver
    
    def upsert_entity(self, entity_id, entity_type, value, canonical_value, confidence, case_id, source_field, start_offset, end_offset):
        def _do_upsert(tx):
            query = """
            MERGE (e:Entity {id: $entity_id})
            ON CREATE SET e.entity_type = $entity_type,
                          e.value = $value,
                          e.canonical_value = $canonical_value,
                          e.confidence = $confidence,
                          e.source_field = $source_field,
                          e.start_offset = $start_offset,
                          e.end_offset = $end_offset
            MERGE (c:Case {case_id: $case_id})
            MERGE (c)-[:CONTAINS]->(e)
            RETURN e, c
            """
            result = tx.run(query, entity_id=entity_id, entity_type=entity_type, 
                            value=value, canonical_value=canonical_value, 
                            confidence=confidence, case_id=case_id, 
                            source_field=source_field, start_offset=start_offset, 
                            end_offset=end_offset)
            record = result.single()
            existed = record is None
            
            case_query = "MATCH (c:Case)-[:CONTAINS]->(e:Entity {id: $entity_id}) RETURN c.case_id AS case_id"
            case_res = tx.run(case_query, entity_id=entity_id)
            case_ids = [r['case_id'] for r in case_res]
            
            return {"existed": existed, "case_ids": case_ids}
            
        with self._driver.session() as session:
            return session.execute_write(_do_upsert)
            
    def entity_exists(self, entity_id) -> bool:
        def _check(tx):
            res = tx.run("MATCH (e:Entity {id: $entity_id}) RETURN count(e) > 0 AS exists", entity_id=entity_id)
            return res.single()['exists']
        with self._driver.session() as session:
            return session.execute_read(_check)
    
    def create_relationship(self, source_entity_id, target_entity_id, relationship_type, source_case_id, confidence, why_linked, relationship_id, evidence_record_id=None):
        def _create(tx):
            query = """
            MATCH (a:Entity {id: $source_entity_id})
            MATCH (b:Entity {id: $target_entity_id})
            MERGE (a)-[r:RELATED {id: $relationship_id}]->(b)
            ON CREATE SET r.relationship_type = $relationship_type,
                          r.source_case_id = $source_case_id,
                          r.confidence = $confidence,
                          r.why_linked = $why_linked,
                          r.evidence_record_id = $evidence_record_id
            RETURN r
            """
            tx.run(query, source_entity_id=source_entity_id, target_entity_id=target_entity_id, 
                   relationship_type=relationship_type, source_case_id=source_case_id, 
                   confidence=confidence, why_linked=why_linked, 
                   relationship_id=relationship_id, evidence_record_id=evidence_record_id)
        with self._driver.session() as session:
            session.execute_write(_create)
    
    def get_cross_case_linkage(self, case_id) -> list[dict]:
        def _linkage(tx):
            query = """
            MATCH (c1:Case {case_id: $case_id})-[:CONTAINS]->(e:Entity)<-[:CONTAINS]-(c2:Case)
            WHERE c2.case_id <> $case_id
            RETURN c2.case_id AS case_id, collect({
                entity_id: e.id,
                entity_type: e.entity_type,
                value: e.value,
                canonical_value: e.canonical_value,
                confidence: e.confidence
            }) AS shared_entities
            """
            result = tx.run(query, case_id=case_id)
            return [record.data() for record in result]
        with self._driver.session() as session:
            return session.execute_read(_linkage)
    
    def get_shortest_path(self, entity_a, entity_b, max_depth=10) -> dict | None:
        def _path(tx):
            query = f"""
            MATCH p = shortestPath((a:Entity {{id: $entity_a}})-[*..{max_depth}]-(b:Entity {{id: $entity_b}}))
            RETURN nodes(p) AS nodes, relationships(p) AS rels
            """
            res = tx.run(query, entity_a=entity_a, entity_b=entity_b)
            record = res.single()
            if not record:
                return None
            nodes = [{'id': n['id'], 'label': n['value'], 'type': n['entity_type']} for n in record['nodes']]
            rels = [{'type': type(r).__name__, 'relationship_type': r.get('relationship_type'), 'confidence': r.get('confidence')} for r in record['rels']]
            return {'nodes': nodes, 'relationships': rels}
        with self._driver.session() as session:
            return session.execute_read(_path)
            
    def get_all_entities(self) -> list[dict]:
        def _get(tx):
            return [r.data()['e'] for r in tx.run("MATCH (e:Entity) RETURN e")]
        with self._driver.session() as session:
            return session.execute_read(_get)
    
    def get_all_relationships(self) -> list[dict]:
        def _get(tx):
            query = """
            MATCH (a:Entity)-[r:RELATED]->(b:Entity)
            RETURN a.id AS source, b.id AS target, r
            """
            return [r.data() for r in tx.run(query)]
        with self._driver.session() as session:
            return session.execute_read(_get)
    
    def get_entity(self, entity_id) -> dict | None:
        def _get(tx):
            res = tx.run("MATCH (e:Entity {id: $entity_id}) RETURN e", entity_id=entity_id)
            rec = res.single()
            return rec['e'] if rec else None
        with self._driver.session() as session:
            return session.execute_read(_get)
    
    def get_case_entities(self) -> dict[str, list[str]]:
        def _get(tx):
            res = tx.run("MATCH (c:Case)-[:CONTAINS]->(e:Entity) RETURN c.case_id AS case, collect(e.id) AS entities")
            return {r['case']: r['entities'] for r in res}
        with self._driver.session() as session:
            return session.execute_read(_get)
            
    def get_entity_case_ids(self, entity_id) -> list[str]:
        def _get(tx):
            res = tx.run("MATCH (c:Case)-[:CONTAINS]->(e:Entity {id: $entity_id}) RETURN c.case_id AS case_id", entity_id=entity_id)
            return [r['case_id'] for r in res]
        with self._driver.session() as session:
            return session.execute_read(_get)
