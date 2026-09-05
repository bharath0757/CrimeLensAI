"""Atomically persist validated CDR/transaction evidence and its graph delivery job."""

import asyncio
import hashlib
import json
from datetime import datetime
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

import httpx
from fastapi import HTTPException
from sqlalchemy import text

from app.core.config import settings
from app.core.entity_identity import normalized_entity_value
from app.repositories.postgres import get_engine
from app.schemas.ingestion import IngestionReceipt


def stable_id(*parts):
    return str(uuid5(NAMESPACE_URL, json.dumps(parts, ensure_ascii=False)))


def receipt(row):
    return IngestionReceipt(**dict(row), graph_total=len(row["graph_operations"]))


async def validate_evidence(kind, case, *, source_text=None, records=None):
    if not settings.SERVICE_AUTH_TOKEN:
        raise HTTPException(503, "Ingestion credentials are not configured")
    payload = {"kind": kind, "case_id": case.id, "case_number": case.case_number}
    payload.update({"csv_text": source_text} if source_text is not None else {"records": records})
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{settings.INGESTION_SERVICE_URL.rstrip('/')}/api/v1/validate", json=payload,
                                         headers={"X-Service-Token": settings.SERVICE_AUTH_TOKEN})
            if response.status_code in {413, 422}:
                raise HTTPException(response.status_code, response.json().get("detail", "Invalid structured evidence"))
            response.raise_for_status()
            result = response.json()
            if result.get("kind") != kind or not isinstance(result.get("records"), list) or not result["records"]:
                raise ValueError("Invalid validation service response")
            return result
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(503, "Structured evidence validation is unavailable") from exc


class StructuredIngestion:
    def __init__(self, engine_factory=get_engine):
        self.engine_factory = engine_factory

    async def get(self, case_id, batch_id):
        def query():
            with self.engine_factory().connect() as connection:
                row = connection.execute(text("SELECT * FROM ingestion_batches WHERE id=:id AND case_id=:case"), {"id": batch_id, "case": case_id}).mappings().first()
                if row is None:
                    raise HTTPException(404, "Ingestion batch not found")
                return receipt(row)
        return await asyncio.to_thread(query)

    async def ingest(self, case_id, actor, kind, validated, source_text, filename):
        if settings.DATA_BACKEND != "postgres":
            raise HTTPException(503, "Structured evidence requires PostgreSQL persistence")
        return await asyncio.to_thread(self._persist, case_id, actor, kind, validated, source_text, filename)

    def _persist(self, case_id, actor, kind, validated, source_text, filename):
        digest = hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        batch_id = stable_id("ingestion", case_id, kind, digest)
        document_id = "doc-" + stable_id("ingestion-source", batch_id)
        operations, entity_ops, inserted = [], {}, 0
        rows = validated["records"]
        with self.engine_factory().begin() as connection:
            # Serialize each case's ingestion against retries and overlapping files.
            connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:case,0))"), {"case": case_id})
            existing = connection.execute(text("SELECT * FROM ingestion_batches WHERE id=:id"), {"id": batch_id}).mappings().first()
            if existing:
                return receipt(existing)
            connection.execute(text("INSERT INTO documents(id,case_id,filename,original_filename,file_type,file_size_bytes,processing_status,uploaded_by) VALUES (:id,:case,:filename,:filename,:file_type,:size,'PROCESSING',:actor)"), {"id": document_id, "case": case_id, "filename": filename, "file_type": "json" if filename.endswith(".json") else "csv", "size": len(source_text.encode()), "actor": actor})

            def occurrence(value, row_number, column):
                return {"document_id": document_id, "source_field": f"{document_id}:row:{row_number}:{column}", "row_number": row_number, "column": column, "value": value, "start_offset": None, "end_offset": None, "source_sha256": digest}

            # Group occurrences before writing: a common hub in 20,000 calls must
            # not rewrite and rehash an ever-growing entity snapshot 20,000 times.
            grouped = {}
            for record in rows:
                fields = [(record["source_type"], record["source"], "caller" if kind == "cdr" else "sender"),
                          (record["target_type"], record["target"], "receiver")]
                fields.append(("LOCATION", record["tower"], "tower") if kind == "cdr" else ("UPI_ID", record["upi"], "upi"))
                for entity_type, value, column in fields:
                    canonical = normalized_entity_value(entity_type, value)
                    group = grouped.setdefault((entity_type, canonical), {"value": value, "occurrences": []})
                    group["occurrences"].append(occurrence(value, record["row_number"], column))
            entity_ids = {}
            for (entity_type, canonical), group in grouped.items():
                entity_ids[(entity_type, canonical)] = connection.execute(text("""INSERT INTO entities(id,case_id,name,normalized_value,entity_type,properties,source_document_id)
                    VALUES (:id,:case,:value,:canonical,:kind,CAST(:properties AS jsonb),:document)
                    ON CONFLICT(case_id,entity_type,normalized_value) DO UPDATE SET
                    properties=entities.properties || jsonb_build_object('occurrences',coalesce(entities.properties->'occurrences','[]'::jsonb) || (EXCLUDED.properties->'occurrences')),updated_at=NOW()
                    RETURNING id"""), {"id": "ent-" + stable_id("case-entity", case_id, entity_type, canonical), "case": case_id,
                    "value": group["value"], "canonical": canonical, "kind": entity_type,
                    "properties": json.dumps({"occurrences": group["occurrences"]}), "document": document_id}).scalar_one()

            def entity(kind_name, value, row_number, column):
                canonical = normalized_entity_value(kind_name, value)
                graph_kind = "PHONE" if kind_name == "PHONE_NUMBER" else kind_name
                graph_id = str(uuid5(NAMESPACE_URL, f"crimelens:entity:{graph_kind}:{canonical}"))
                key = (graph_id, row_number, column)
                entity_ops[key] = {"kind": "entity", "payload": {"case_id": case_id, "entity_id": graph_id, "entity_type": graph_kind, "value": value, "normalized_value": canonical, "confidence": 1.0, "source_field": occurrence(value, row_number, column)["source_field"]}}
                return entity_ids[(kind_name, canonical)], graph_id

            def relationship(source, target, relation, record, explanation):
                identifier = "rel-" + stable_id(case_id, kind, record["record_id"], relation)
                evidence_key = "cdr_id" if kind == "cdr" else "transaction_id"
                properties = {evidence_key: record["record_id"], "timestamp": record["timestamp"], "row_number": record["row_number"], "source_sha256": digest}
                properties.update({key: record[key] for key in ("amount", "duration", "tower", "imei", "upi", "transaction_type", "description") if record.get(key) is not None})
                properties["occurrences"] = [{"document_id": document_id, "row_number": record["row_number"], "source_sha256": digest,
                                               "metadata": {key: record[key] for key in ("transaction_type", "description") if record.get(key) is not None}}]
                connection.execute(text("""INSERT INTO relationships(id,case_id,source_entity_id,target_entity_id,relationship_type,description,properties,source_document_id)
                    VALUES (:id,:case,:source,:target,:type,:description,CAST(:properties AS jsonb),:document)
                    ON CONFLICT(id) DO UPDATE SET properties=relationships.properties || jsonb_build_object(
                    'occurrences',coalesce(relationships.properties->'occurrences','[]'::jsonb) || (EXCLUDED.properties->'occurrences')),updated_at=NOW()"""),
                    {"id": identifier, "case": case_id, "source": source[0], "target": target[0], "type": relation, "description": explanation, "properties": json.dumps(properties), "document": document_id})
                evidence = {key: record[key] for key in ("timestamp", "amount", "duration", "tower", "imei", "upi") if record.get(key) is not None}
                if kind == "transactions":
                    evidence["currency"] = "INR"
                evidence["sources"] = [{"document_id": document_id, "row_number": record["row_number"], "source_sha256": digest}]
                operations.append({"kind": "relationship", "payload": {"source_entity_id": source[1], "target_entity_id": target[1], "relationship_type": relation, "source_case_id": case_id, "confidence": 1.0, "why_linked": explanation, "evidence_record_id": record["record_id"], "evidence": evidence}})

            for record in rows:
                if kind == "cdr":
                    table, key = "cdr_records", "cdr_id"
                    values = {"cdr_id": record["record_id"], "case_id": case_id, "caller": record["source"], "receiver": record["target"], "occurred_at": datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00")), "duration_seconds": record["duration"], "tower": record["tower"], "imei": record["imei"]}
                else:
                    table, key = "transactions", "transaction_id"
                    values = {"transaction_id": record["record_id"], "case_id": case_id, "sender": record["source"], "receiver": record["target"], "amount": Decimal(record["amount"]), "upi_id": record["upi"], "occurred_at": datetime.fromisoformat(record["timestamp"].replace("Z", "+00:00"))}
                prior = connection.execute(text(f"SELECT * FROM {table} WHERE case_id=:case_id AND {key}=:{key}"), values).mappings().first()
                if prior:
                    prior = dict(prior)
                    if kind == "cdr":
                        for column in ("caller", "receiver"):
                            prior[column] = normalized_entity_value("PHONE_NUMBER", prior[column])
                    if any(prior[column] != value for column, value in values.items()):
                        raise HTTPException(409, f"Evidence ID {record['record_id']} already has different contents; no rows imported")
                else:
                    connection.execute(text(f"INSERT INTO {table} ({','.join(values)}) VALUES ({','.join(':'+column for column in values)})"), values)
                    inserted += 1
                number = record["row_number"]
                source = entity(record["source_type"], record["source"], number, "caller" if kind == "cdr" else "sender")
                target = entity(record["target_type"], record["target"], number, "receiver")
                relationship(source, target, "CALLED" if kind == "cdr" else "TRANSFERRED_TO", record,
                             f"Observed in {kind} source {document_id}, row {number}; reference {record['record_id']}. Record authenticity and attribution require officer review.")
                if kind == "cdr":
                    tower = entity("LOCATION", record["tower"], number, "tower")
                    relationship(source, tower, "LOCATED_AT", record, f"Call record row {number} reports tower {record['tower']}; this is tower-level routing evidence, not a person's precise location.")
                else:
                    entity("UPI_ID", record["upi"], number, "upi")
            relationship_count = len(operations)
            operations = list(entity_ops.values()) + operations
            connection.execute(text("UPDATE documents SET extracted_entity_count=:entities,extracted_relationship_count=:relationships WHERE id=:id"),
                               {"entities": len(entity_ids), "relationships": relationship_count, "id": document_id})
            connection.execute(text("UPDATE cases SET entity_count=(SELECT count(*) FROM entities WHERE case_id=:case),relationship_count=(SELECT count(*) FROM relationships WHERE case_id=:case),document_count=(SELECT count(*) FROM documents WHERE case_id=:case),updated_at=NOW() WHERE id=:case"), {"case": case_id})
            row = connection.execute(text("""INSERT INTO ingestion_batches(id,case_id,document_id,kind,source_sha256,source_text,actor,record_count,inserted_records,duplicate_records,graph_operations)
                VALUES (:id,:case,:document,:kind,:hash,:source,:actor,:count,:inserted,:duplicates,CAST(:operations AS jsonb)) RETURNING *"""), {"id": batch_id, "case": case_id, "document": document_id, "kind": kind, "hash": digest, "source": source_text, "actor": actor, "count": len(rows), "inserted": inserted, "duplicates": validated["input_rows"] - inserted, "operations": json.dumps(operations)}).mappings().one()
            return receipt(row)


structured_ingestion = StructuredIngestion()
