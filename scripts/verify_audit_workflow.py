"""HTTP smoke test for automatic case audit delivery in an isolated environment."""

import argparse
import json
import os
import time

import httpx
from sqlalchemy.engine import make_url


def verify(base_url: str) -> dict:
    database_name = make_url(os.environ["DATABASE_URL"]).database or ""
    if os.environ.get("VERIFICATION_SCOPE") != "isolated-synthetic" or not database_name.endswith("_verify"):
        raise RuntimeError("Use only the isolated synthetic verification database")
    with httpx.Client(base_url=base_url.rstrip("/"), timeout=15) as client:
        health = client.get("/api/v1/health")
        health.raise_for_status()
        assert health.json()["data_backend"] == "postgres"
        assert health.json()["audit_delivery"] == "running"
        login = client.post("/api/v1/auth/login", json={
            "email": os.environ["AUDIT_SMOKE_EMAIL"],
            "password": os.environ["AUDIT_SMOKE_PASSWORD"],
        })
        login.raise_for_status()
        identity = login.json()
        client.headers.update({"Authorization": f"Bearer {identity['access_token']}", "X-Actor": "forged-test-actor"})
        created = client.post("/api/v1/cases", json={
            "title": "Isolated automatic audit verification",
            "description": "Synthetic case created and removed by the audit smoke test.",
        })
        assert created.status_code == 201, created.text
        case_id = created.json()["id"]
        try:
            records = []
            for _ in range(40):
                chain = client.get("/api/v1/ledger/chain", params={"case_id": case_id})
                chain.raise_for_status()
                records = chain.json()["items"]
                if records:
                    break
                time.sleep(.2)
            assert len(records) == 1, "Automatic case audit event was not delivered exactly once"
            record = records[0]
            assert record["actor"] == identity["user"]["id"]
            assert record["action"] == "CASE_INSERT"
            assert record["verified"] is None
            result = client.get(f"/api/v1/ledger/verify/{record['id']}", params={"case_id": case_id})
            result.raise_for_status()
            assert result.json()["verified"] is True
            return {"automatic_delivery": True, "officer_attributed": True, "verified": True}
        finally:
            removed = client.delete(f"/api/v1/cases/{case_id}")
            assert removed.status_code == 204, "Failed to remove the synthetic test case"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    arguments = parser.parse_args()
    print(json.dumps(verify(arguments.base_url)))
