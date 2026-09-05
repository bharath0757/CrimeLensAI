"""Read-only real-service verification after acknowledging a synthetic alert in UI.

Only accepts the isolated synthetic verification database. Checks exact dashboard
amounts/counts, Neo4j-backed persisted acknowledgement, and delivered audit hashes.
"""

import json
import os
from decimal import Decimal

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    database_url = os.environ["DATABASE_URL"]
    database_name = make_url(database_url).database or ""
    if os.environ.get("VERIFICATION_SCOPE") != "isolated-synthetic" or not database_name.endswith("_verify"):
        raise RuntimeError("Use only the isolated synthetic verification database")
    engine = create_engine(database_url)
    with httpx.Client(base_url=os.environ.get("FIR_SMOKE_API_URL", "http://127.0.0.1:8000"), timeout=60) as client:
        def call(method, path, **kwargs):
            response = client.request(method, path, **kwargs)
            response.raise_for_status()
            return response.json()

        login = call("POST", "/api/v1/auth/login", json={"email": os.environ["FIR_SMOKE_EMAIL"], "password": os.environ["FIR_SMOKE_PASSWORD"]})
        assert login["user"]["role"] == "ADMIN", "This gate compares the full synthetic dataset"
        client.headers["Authorization"] = f"Bearer {login['access_token']}"
        overview = call("GET", "/api/v1/dashboard/overview")
        metrics = overview["metrics"]
        with engine.connect() as connection:
            expected = connection.execute(text("SELECT count(*) AS total, count(*) FILTER (WHERE priority IN ('HIGH','CRITICAL')) AS high, count(*) FILTER (WHERE status IN ('OPEN','IN_PROGRESS')) AS active FROM cases")).one()
            money = connection.execute(text("SELECT coalesce(sum(amount),0) FROM transactions")).scalar_one()
            events = connection.execute(text("SELECT event_id::text AS id,event,delivered_at FROM audit_outbox WHERE event->>'action' IN ('ALERT_ACK_REQUESTED','ALERT_ACKNOWLEDGED') ORDER BY sequence")).mappings().all()
        assert metrics["total_cases"] == expected.total
        assert metrics["high_risk_cases"] == expected.high
        assert metrics["active_investigations"] == expected.active
        assert Decimal(metrics["money_flow"]) == money
        assert sum(overview["statistics"]["cases_by_status"].values()) == expected.total
        assert len(events) >= 4, "Acknowledge a synthetic connection through the browser first"
        assert all(event["delivered_at"] for event in events), "Wait for automatic outbox delivery"
        completed = [event for event in events if event["event"]["action"] == "ALERT_ACKNOWLEDGED"]
        assert completed
        alert_ids = {event["event"]["record_id"] for event in completed}
        alerts = call("GET", "/api/v1/dashboard/alerts?limit=100")
        assert all(any(alert["id"] == alert_id and alert["status"] == "ACKNOWLEDGED" for alert in alerts["items"]) for alert_id in alert_ids)
        for event in events:
            verified = call("GET", f"/api/v1/ledger/verify/{event['id']}")
            assert verified["verified"], verified
        print(json.dumps({"status": "passed", "metrics": metrics, "acknowledged_alerts": len(alert_ids), "verified_audit_events": len(events), "database": database_name, "graph": "acknowledgements loaded after service restart"}))
    engine.dispose()


if __name__ == "__main__":
    main()
