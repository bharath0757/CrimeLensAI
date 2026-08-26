# Neo4j Schema Documentation

CrimeLensAI uses a provenance-first graph. A canonical entity is shared across
cases, while each `HAS_ENTITY` edge retains the source occurrence that caused
the association.

```text
(:Case {case_id})
  -[:HAS_ENTITY {source_field, start_offset, end_offset, confidence, observed_value}]->
(:Entity {id, entity_type, value, canonical_value, confidence})

(:Entity)-[:RELATED {
  id, relationship_type, source_case_id, confidence,
  why_linked, evidence_record_id
}]->(:Entity)

(:LinkAlert {
  id, case_ids, shared_entity_ids, severity, status,
  title, explanation, created_at
})
```

Recommended constraints:

```cypher
CREATE CONSTRAINT case_id_unique IF NOT EXISTS
FOR (c:Case) REQUIRE c.case_id IS UNIQUE;

CREATE CONSTRAINT entity_id_unique IF NOT EXISTS
FOR (e:Entity) REQUIRE e.id IS UNIQUE;

CREATE CONSTRAINT alert_id_unique IF NOT EXISTS
FOR (a:LinkAlert) REQUIRE a.id IS UNIQUE;

CREATE INDEX entity_canonical_lookup IF NOT EXISTS
FOR (e:Entity) ON (e.entity_type, e.canonical_value);
```

`canonical_value` is produced by the extraction service. Phone, UPI and vehicle
identity is exact after normalization; ambiguous person-name resolution remains
a human-confirmed candidate merge.
