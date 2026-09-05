"""Verify existing synthetic financial evidence in a newly hydrated graph process."""

import json
import os
import sys
from decimal import Decimal

from app.core.neo4j import neo4j_manager
from app.store import Neo4jGraphStore


def main():
    if os.environ.get("VERIFICATION_SCOPE") != "isolated-synthetic":
        raise RuntimeError("Run only against the isolated synthetic verification graph")
    if len(sys.argv) != 2:
        raise ValueError("Pass the case ID from verify_structured_workflow.py")
    case_id = sys.argv[1]
    neo4j_manager.connect()
    try:
        store = Neo4jGraphStore()
        store.hydrate()
        relationships = [item for item in store.relationships.values() if item["source_case_id"] == case_id]
        transfers = [item for item in relationships if item["relationship_type"] == "TRANSFERRED_TO"]
        assert len(transfers) == 2
        assert sum(Decimal(item["evidence"]["amount"]) for item in transfers) == Decimal("200.00")
        assert all(item["evidence"]["currency"] == "INR" for item in transfers)
        for item in relationships:
            source = item["evidence"]["sources"][0]
            assert source["row_number"] >= 2 and len(source["source_sha256"]) == 64
            assert source["document_id"].startswith("doc-")
        print(json.dumps({"case_id": case_id, "financial_metadata_survived_restart": True,
                          "exact_amount": "200.00", "source_references_survived_restart": True}))
    finally:
        neo4j_manager.close()


if __name__ == "__main__":
    main()
