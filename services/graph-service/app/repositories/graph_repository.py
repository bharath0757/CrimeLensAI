from __future__ import annotations

import uuid

ENTITY_LABELS = {
    "PERSON", "PHONE", "VEHICLE", "LOCATION", "BANK", "BANK_ACCOUNT",
    "UPI_ID", "ORG", "AADHAAR", "PAN", "PASSPORT", "EMAIL", "DATE",
    "IPC_SECTION",
}
RELATIONSHIP_TYPES = {
    "CALLED", "TRANSFERRED_TO", "OWNS", "LOCATED_AT", "INVOLVED_IN",
    "USES", "WORKS_FOR", "CONTACTED", "TRANSACTED", "CO_LOCATED",
    "RELATED", "ASSOCIATED", "USED_PHONE", "CO_OCCURS",
    "COMMUNICATED_WITH", "TRANSFERRED_FUNDS", "HAS_ACCOUNT", "REGISTERED_TO",
}

class GraphRepository:
    def __init__(self, driver):
        self._driver = driver
    
    def upsert_entity(self, entity_id, entity_type, value, canonical_value, confidence, case_id, source_field, start_offset, end_offset):
        if entity_type not in ENTITY_LABELS:
            raise ValueError(f"Unsupported entity label: {entity_type}")
        occurrence_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{entity_id}:{case_id}:{source_field}:{start_offset}:{end_offset}"))
        domain_label = "UPI" if entity_type == "UPI_ID" else entity_type
        def _do_upsert(tx):
            query = f"""
            OPTIONAL MATCH (existing:Entity {{id: $entity_id}})
            WITH existing IS NOT NULL AS existed
            MERGE (e:Entity:`{entity_type}` {{id: $entity_id}})
            ON CREATE SET e.entity_type = $entity_type,
                          e.value = $value,
                          e.canonical_value = $canonical_value,
                          e.confidence = $confidence,
                          e.source_field = $source_field,
                          e.start_offset = $start_offset,
                          e.end_offset = $end_offset
            SET e:`{domain_label}`,
                e.confidence = CASE WHEN e.confidence < $confidence THEN $confidence ELSE e.confidence END
            MERGE (c:Case {{case_id: $case_id}})
            SET c:CASE
            MERGE (e)-[o:INVOLVED_IN {{occurrence_id: $occurrence_id}}]->(c)
            SET o.source_field = $source_field, o.start_offset = $start_offset,
                o.end_offset = $end_offset, o.confidence = $confidence,
                o.observed_value = $value
            RETURN e, c, existed
            """
            result = tx.run(query, entity_id=entity_id, entity_type=entity_type, 
                            value=value, canonical_value=canonical_value, 
                            confidence=confidence, case_id=case_id, 
                            source_field=source_field, start_offset=start_offset, 
                            end_offset=end_offset, occurrence_id=occurrence_id)
            record = result.single()
            existed = record["existed"] if record else False
            
            case_query = "MATCH (e:Entity {id: $entity_id})-[:INVOLVED_IN]->(c:Case) RETURN c.case_id AS case_id"
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
    
    def create_relationship(self, source_entity_id, target_entity_id, relationship_type, source_case_id, confidence, why_linked, relationship_id, evidence_record_id=None, evidence=None):
        import json
        from decimal import Decimal

        if relationship_type not in RELATIONSHIP_TYPES:
            raise ValueError(f"Unsupported relationship type: {relationship_type}")
        amount_minor = int(Decimal(evidence["amount"]) * 100) if evidence and evidence.get("amount") is not None else None
        def _create(tx):
            query = f"""
            MATCH (a:Entity {{id: $source_entity_id}})
            MATCH (b:Entity {{id: $target_entity_id}})
            MERGE (a)-[r:`{relationship_type}` {{id: $relationship_id}}]->(b)
            ON CREATE SET r.relationship_type = $relationship_type,
                          r.source_case_id = $source_case_id,
                          r.confidence = $confidence,
                          r.why_linked = $why_linked,
                          r.evidence_record_id = $evidence_record_id
            SET r.evidence_json = coalesce($evidence_json, r.evidence_json),
                r.amount_minor = coalesce($amount_minor, r.amount_minor),
                r.currency = coalesce($currency, r.currency),
                r.occurred_at = coalesce($occurred_at, r.occurred_at)
            RETURN r
            """
            result = tx.run(query, source_entity_id=source_entity_id, target_entity_id=target_entity_id,
                   relationship_type=relationship_type, source_case_id=source_case_id, 
                   confidence=confidence, why_linked=why_linked, 
                   relationship_id=relationship_id, evidence_record_id=evidence_record_id,
                   evidence_json=json.dumps(evidence, sort_keys=True) if evidence else None,
                   amount_minor=amount_minor, currency=evidence.get("currency") if evidence else None,
                   occurred_at=evidence.get("timestamp") if evidence else None)
            if result.single() is None:
                raise ValueError("Both relationship endpoints must exist in Neo4j")
        with self._driver.session() as session:
            session.execute_write(_create)
    
    def get_cross_case_linkage(self, case_id) -> list[dict]:
        def _linkage(tx):
            query = """
            MATCH (c1:Case)<-[:INVOLVED_IN]-(e:Entity)-[:INVOLVED_IN]->(c2:Case)
            WHERE c1.case_id = $case_id
              AND c2.case_id <> $case_id
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
            MATCH (a:Entity)-[r]->(b:Entity)
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
            res = tx.run("MATCH (e:Entity)-[:INVOLVED_IN]->(c:Case) RETURN c.case_id AS case, collect(e.id) AS entities")
            return {r['case']: r['entities'] for r in res}
        with self._driver.session() as session:
            return session.execute_read(_get)
            
    def get_entity_case_ids(self, entity_id) -> list[str]:
        def _get(tx):
            res = tx.run("MATCH (e:Entity {id: $entity_id})-[:INVOLVED_IN]->(c:Case) RETURN c.case_id AS case_id", entity_id=entity_id)
            return [r['case_id'] for r in res]
        with self._driver.session() as session:
            return session.execute_read(_get)
