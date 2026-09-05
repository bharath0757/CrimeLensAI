from app.analysis import FirAnalysisService
from app.models import (
    EntityInput,
    EntityType,
    FirAnalysisRequest,
    RawFirInput,
    RelationshipInput,
)
from app.store import InMemoryGraphStore


def add(store, case_id, entity_type, value, confidence=0.95):
    return store.upsert_entity(EntityInput(
        entity_type=entity_type,
        value=value,
        confidence=confidence,
        case_id=case_id,
        source_field="fir_text",
        start_offset=10,
        end_offset=20,
    ))


def test_shared_identifier_creates_linkage_and_alert():
    store = InMemoryGraphStore()
    first = add(store, "FIR-001", EntityType.PHONE, "+91 98765 43210")
    second = add(store, "FIR-002", EntityType.PHONE, "9876543210")

    assert first["entity"]["id"] == second["entity"]["id"]
    linkage = store.get_linkage("FIR-001")
    assert linkage["linked_cases"][0]["case_id"] == "FIR-002"
    assert linkage["linked_cases"][0]["link_strength"] > 0.5
    assert store.list_alerts()[0]["severity"] == "HIGH"


def test_multi_signal_pattern_is_explainable():
    store = InMemoryGraphStore()
    for case_id in ("FIR-001", "FIR-002"):
        add(store, case_id, EntityType.PHONE, "9876543210")
        add(store, case_id, EntityType.VEHICLE, "UP 32 AB 1234")
    patterns = store.patterns("FIR-001")["patterns"]
    assert patterns[0]["pattern_type"] == "MULTI_SIGNAL_CONVERGENCE"
    assert patterns[0]["disposition"] == "INVESTIGATIVE_LEAD_NOT_FACT"


def test_shortest_path_keeps_relationship_explanation():
    store = InMemoryGraphStore()
    a = add(store, "FIR-001", EntityType.PERSON, "Ananya Sharma")["entity"]["id"]
    b = add(store, "FIR-001", EntityType.PHONE, "9876543210")["entity"]["id"]
    store.create_relationship(RelationshipInput(
        source_entity_id=a,
        target_entity_id=b,
        relationship_type="USED_PHONE",
        source_case_id="FIR-001",
        confidence=0.9,
        why_linked="The FIR states that this phone was used by the named person.",
    ))
    path = store.shortest_path(a, b)
    assert path["steps"][0]["relationship_type"] == "USED_PHONE"


def test_ground_truth_signals_become_bridge_patterns():
    exact_signals = {
        "UP32AB1234": ["FIR-LKO-001", "FIR-BBK-002", "FIR-AYD-004"],
        "9876543210": ["FIR-LKO-001", "FIR-STP-003", "FIR-UNN-005"],
        "safehouse@ybl": ["FIR-BBK-002", "FIR-STP-003", "FIR-AYD-004"],
    }
    type_by_signal = {
        "UP32AB1234": EntityType.VEHICLE,
        "9876543210": EntityType.PHONE,
        "safehouse@ybl": EntityType.UPI_ID,
    }
    store = InMemoryGraphStore()
    for signal, case_ids in exact_signals.items():
        for case_id in case_ids:
            add(store, case_id, type_by_signal[signal], signal)

    bridge_patterns = []
    for case_id in {case for cases in exact_signals.values() for case in cases}:
        bridge_patterns.extend(
            pattern for pattern in store.patterns(case_id)["patterns"]
            if pattern["pattern_type"] == "BRIDGE_ENTITY"
        )
    assert len({pattern["supporting_entity_ids"][0] for pattern in bridge_patterns}) == 3


def test_random_raw_firs_produce_officer_ready_connection_report():
    def fake_extractor(firs):
        results = []
        for fir in firs:
            phone_start = fir["raw_text"].index("9988776655")
            results.append({
                "case_id": fir["case_id"],
                "district": fir.get("district"),
                "fir_number": fir.get("fir_number"),
                "entities": [{
                    "entity_type": "PHONE",
                    "value": "9988776655",
                    "canonical_value": "9988776655",
                    "confidence": 0.99,
                    "start_offset": phone_start,
                    "end_offset": phone_start + 10,
                    "source_field": "fir_text",
                }],
                "warnings": [],
            })
        return {"results": results, "warnings": []}

    service = FirAnalysisService(InMemoryGraphStore(), extractor=fake_extractor)
    report = service.analyze(FirAnalysisRequest(firs=[
        RawFirInput(case_id="RANDOM-001", district="Mysuru", raw_text="Victim Nisha Rao called 9988776655."),
        RawFirInput(case_id="RANDOM-002", district="Mandya", raw_text="Witness Arun Das recorded 9988776655."),
    ]))

    assert report["status"] == "COMPLETED"
    assert report["cases_processed"] == 2
    assert report["alerts"][0]["severity"] == "HIGH"
    assert report["cross_case_links"][0]["case_ids"] == ["RANDOM-001", "RANDOM-002"]
    assert "high-priority" in report["officer_brief"]["summary"]
    assert report["officer_brief"]["decision_boundary"].endswith("not findings of guilt.")
