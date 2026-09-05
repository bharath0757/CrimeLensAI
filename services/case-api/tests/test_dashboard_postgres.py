"""Exact dashboard totals and authorization against an isolated PostgreSQL schema."""

import asyncio
import os
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.schemas.dashboard import ConnectionAlert
from app.schemas.user import UserResponse
from app.services.alerts import audit_alert_action
from app.services.dashboard import DashboardService

TEST_URL = os.getenv("CASE_API_TEST_POSTGRES_URL")
pytestmark = pytest.mark.skipif(not TEST_URL, reason="Requires isolated PostgreSQL integration database")


def officer(role="INVESTIGATOR", identifier="officer"):
    return UserResponse(id=identifier, email=f"{identifier}@test.example", full_name="Test Officer",
                        role=role, created_at=datetime.now(UTC), updated_at=datetime.now(UTC))


def seed_visible_cases(database):
    with database.begin() as connection:
        connection.execute(text("INSERT INTO users(id,email,password_hash,full_name,role) VALUES ('officer','officer@test.example','not-login','Officer','INVESTIGATOR')"))
        for case_id, owner, assigned, priority, status in [
            ("a", "officer", '[]', "HIGH", "OPEN"),
            ("b", "test-admin", '["officer"]', "LOW", "IN_PROGRESS"),
            ("c", "officer", '[]', "LOW", "CLOSED"),
            ("d", "officer", '[]', "LOW", "OPEN"),
            ("hidden", "test-admin", '[]', "CRITICAL", "OPEN"),
        ]:
            connection.execute(text("INSERT INTO cases(id,case_number,title,description,owner_id,assigned_investigator_ids,priority,status) VALUES (:id,:id,'Synthetic case','Synthetic description',:owner,CAST(:assigned AS jsonb),:priority,:status)"),
                               {"id": case_id, "owner": owner, "assigned": assigned, "priority": priority, "status": status})
        for index, (case_id, kind, value, review) in enumerate([
            ("a", "PHONE_NUMBER", "9000990189", "PENDING"), ("b", "PHONE_NUMBER", "9000990189", "CONFIRMED"),
            ("c", "EMAIL", "shared@example.test", "PENDING"), ("d", "EMAIL", "shared@example.test", "CONFIRMED"),
            ("a", "LOCATION", "Lucknow", "PENDING"), ("c", "LOCATION", "Lucknow", "PENDING"),
            ("a", "BANK_ACCOUNT", "123456789", "REJECTED"), ("c", "BANK_ACCOUNT", "123456789", "REJECTED"),
            ("hidden", "PHONE_NUMBER", "9000990189", "PENDING"),
        ]):
            connection.execute(text("INSERT INTO entities(id,case_id,name,normalized_value,entity_type,review_status) VALUES (:id,:case,:value,:value,:kind,:review)"),
                               {"id": f"e{index}", "case": case_id, "value": value, "kind": kind, "review": review})
        for case_id, amount in [("a", "125.50"), ("b", "24.25"), ("hidden", "900000.99")]:
            connection.execute(text("INSERT INTO transactions VALUES (:id,:id,'bank-a','bank-b',:amount,'synthetic@upi','2026-08-12T12:00:00Z')"), {"id": case_id, "amount": Decimal(amount)})


def test_scoped_metrics_include_assigned_cases_not_hidden_money(database, monkeypatch):
    monkeypatch.setattr(settings, "DATA_BACKEND", "postgres")
    seed_visible_cases(database)
    result = asyncio.run(DashboardService(engine_factory=lambda: database).overview(officer()))
    assert result.metrics.total_cases == 4
    assert result.metrics.high_risk_cases == 1
    assert result.metrics.active_investigations == 3
    assert result.metrics.money_flow == Decimal("149.75")
    assert result.metrics.linked_networks == 2  # Location/rejected IDs do not collapse the two networks.
    assert result.metrics.total_entities == 8
    assert result.metrics.pending_reviews == 4
    assert result.statistics.cases_by_status == {"OPEN": 2, "IN_PROGRESS": 1, "CLOSED": 1}
    assert result.statistics.transaction_timeline[0].amount == Decimal("149.75")
    assert result.statistics.transaction_timeline[0].count == 2
    assert all(event["case_id"] != "hidden" for event in result.statistics.recent_activities)
    admin = asyncio.run(DashboardService(engine_factory=lambda: database).overview(officer("ADMIN", "test-admin")))
    assert admin.metrics.total_cases == 5
    assert admin.metrics.money_flow == Decimal("900150.74")
    assert admin.metrics.high_risk_cases == 2


def test_totals_and_charts_are_not_limited_to_one_case_page(database, monkeypatch):
    monkeypatch.setattr(settings, "DATA_BACKEND", "postgres")
    with database.begin() as connection:
        connection.execute(text("INSERT INTO cases(id,case_number,title,description,owner_id,priority) SELECT 'page-'||i,'page-'||i,'Synthetic page test','Narrative','test-admin','HIGH' FROM generate_series(1,225) i"))
    result = asyncio.run(DashboardService(engine_factory=lambda: database).overview(officer("ADMIN", "test-admin")))
    assert result.metrics.total_cases == 225
    assert result.statistics.cases_by_priority == {"HIGH": 225}
    assert result.metrics.money_flow == Decimal(0)
    assert result.metrics.linked_networks == 0


def test_acknowledgement_audit_is_case_scoped_and_retry_safe(database, monkeypatch):
    monkeypatch.setattr(settings, "DATA_BACKEND", "postgres")
    alert = ConnectionAlert(id="alert-1", case_ids=["a", "b"], severity="HIGH", status="ACKNOWLEDGED",
                            title="Synthetic link", explanation="Shared synthetic phone", created_at=datetime.now(UTC))
    asyncio.run(audit_alert_action(alert, officer(), "ALERT_ACKNOWLEDGED"))
    asyncio.run(audit_alert_action(alert, officer(), "ALERT_ACKNOWLEDGED"))
    with database.connect() as connection:
        events = connection.execute(text("SELECT event FROM audit_outbox")).scalars().all()
    assert len(events) == 2
    assert {event["case_id"] for event in events} == {"a", "b"}
    assert all(event["actor"] == "officer" and event["action"] == "ALERT_ACKNOWLEDGED" for event in events)
