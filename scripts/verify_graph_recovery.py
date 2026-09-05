"""Read back existing synthetic FIR links and mentions from a fresh Neo4j store."""

import json
import os
import sys

from app.core.neo4j import neo4j_manager
from app.store import Neo4jGraphStore


def main():
    if os.environ.get("VERIFICATION_SCOPE") != "isolated-synthetic":
        raise RuntimeError("This check targets only the isolated verification database")
    case_ids = set(sys.argv[1:])
    if len(case_ids) != 2:
        raise ValueError("Pass the two previously created synthetic case IDs")
    neo4j_manager.connect()
    try:
        store = Neo4jGraphStore()
        store.hydrate()
        first, second = sorted(case_ids)
        linked = store.get_linkage(first)
        match = next(item for item in linked["linked_cases"] if item["case_id"] == second)
        assert match["explanation"]
        for kind, value in (("PHONE", "9000990189"), ("UPI_ID", "demo26189@upi")):
            entity = next(item for item in match["shared_entities"] if item["entity_type"] == kind and item["canonical_value"] == value)
            occurrences = [item for item in entity["occurrences"] if item["case_id"] in case_ids]
            assert {item["case_id"] for item in occurrences} == case_ids
            assert all(item["source_field"] != "unknown" and isinstance(item["start_offset"], int)
                       and item["end_offset"] > item["start_offset"] for item in occurrences)
        assert any(case_ids.issubset(alert["case_ids"]) for alert in store.alerts.values())
        print(json.dumps({"existing_link_survived_restart": True, "source_offsets_survived_restart": True, "alert_survived_restart": True}))
    finally:
        neo4j_manager.close()


if __name__ == "__main__":
    main()
