import re
with open('services/graph-service/app/repositories/graph_repository.py', 'r') as f:
    content = f.read()

new_upsert = '''        def _do_upsert(tx):
            query = """
            OPTIONAL MATCH (existing:Entity {id: $entity_id})
            WITH existing IS NOT NULL AS existed
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
            RETURN e, c, existed
            """
            result = tx.run(query, entity_id=entity_id, entity_type=entity_type, 
                            value=value, canonical_value=canonical_value, 
                            confidence=confidence, case_id=case_id, 
                            source_field=source_field, start_offset=start_offset, 
                            end_offset=end_offset)
            record = result.single()
            existed = record["existed"] if record else False
            
            case_query = "MATCH (c:Case)-[:CONTAINS]->(e:Entity {id: $entity_id}) RETURN c.case_id AS case_id"
            case_res = tx.run(case_query, entity_id=entity_id)
            case_ids = [r['case_id'] for r in case_res]
            
            return {"existed": existed, "case_ids": case_ids}'''

content = re.sub(r'        def _do_upsert\(tx\):.*?return \{"existed": existed, "case_ids": case_ids\}', new_upsert, content, flags=re.DOTALL)

with open('services/graph-service/app/repositories/graph_repository.py', 'w') as f:
    f.write(content)
