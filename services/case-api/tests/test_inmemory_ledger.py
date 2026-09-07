"""Unit tests for InMemoryLedgerStore."""

import pytest
from fastapi import HTTPException

from app.integrations.ledger_integration import InMemoryLedgerStore, record_hash


def test_append_and_chain():
    store = InMemoryLedgerStore()
    ev1 = store.append({
        "event_id": "ev-1", "record_id": "case-1", "case_id": "case-1",
        "actor": "admin", "action": "CASE_CREATED", "resource_type": "CASE",
        "payload": {"title": "Phishing investigation"},
    })
    assert ev1["sequence"] == 1
    assert ev1["previous_hash"] == "0" * 64
    assert ev1["hash"] == record_hash(ev1)

    ev2 = store.append({
        "event_id": "ev-2", "record_id": "case-2", "case_id": "case-2",
        "actor": "investigator", "action": "CASE_CREATED", "resource_type": "CASE",
        "payload": {"title": "Marketplace fraud"},
    })
    assert ev2["sequence"] == 2
    assert ev2["previous_hash"] == ev1["hash"]
    assert ev2["hash"] == record_hash(ev2)

    chain = store.chain(limit=10, offset=0)
    assert chain.total == 2
    assert len(chain.records) == 2
    assert chain.records[0].sequence == 2
    assert chain.records[1].sequence == 1


def test_chain_filter_by_case():
    store = InMemoryLedgerStore()
    store.append({"event_id": "e1", "record_id": "c1", "case_id": "case-A", "action": "A"})
    store.append({"event_id": "e2", "record_id": "c2", "case_id": "case-B", "action": "B"})
    store.append({"event_id": "e3", "record_id": "c3", "case_id": "case-A", "action": "C"})

    chain_a = store.chain(case_ids=["case-A"])
    assert chain_a.total == 2
    assert all(r.case_id == "case-A" for r in chain_a.records)

    chain_b = store.chain(case_ids=["case-B"])
    assert chain_b.total == 1
    assert chain_b.records[0].case_id == "case-B"


def test_verify_intact_chain():
    store = InMemoryLedgerStore()
    store.append({"event_id": "e1", "record_id": "rec-1", "case_id": "case-1", "action": "A"})
    store.append({"event_id": "e2", "record_id": "rec-2", "case_id": "case-1", "action": "B"})
    store.append({"event_id": "e3", "record_id": "rec-3", "case_id": "case-1", "action": "C"})

    res = store.verify("e2")
    assert res.verified is True
    assert res.status == "VERIFIED"
    assert res.checked_records == 3
    assert res.error_sequence is None


def test_verify_tamper_detection():
    store = InMemoryLedgerStore()
    store.append({"event_id": "e1", "record_id": "rec-1", "case_id": "case-1", "action": "A"})
    store.append({"event_id": "e2", "record_id": "rec-2", "case_id": "case-1", "action": "B"})
    store.append({"event_id": "e3", "record_id": "rec-3", "case_id": "case-1", "action": "C"})

    # Tamper with entry 2 payload
    store._entries[1]["payload"] = {"tampered": True}

    res = store.verify("e3")
    assert res.verified is False
    assert res.status == "TAMPERED"
    assert res.error_sequence == 2
