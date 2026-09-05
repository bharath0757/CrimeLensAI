import asyncio
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException

from app.repositories.case_repo import InMemoryCaseRepository
from app.schemas.case import CaseCreate
from app.schemas.user import UserResponse
from app.services.alerts import AlertService
from app.services.dashboard import count_linked_networks


def test_network_count_is_transitive_and_ignores_singletons():
    assert count_linked_networks([["a", "b"], ["b", "c"], ["d", "e"], ["f"]]) == 2


def user(role="INVESTIGATOR"):
    return UserResponse(id="officer", email="officer@test.example", full_name="Test Officer", role=role,
                        created_at=datetime.now(UTC), updated_at=datetime.now(UTC))


async def scoped_service(offline=False):
    repository = InMemoryCaseRepository()
    repository._cases.clear()
    case_ids = []
    for owner in ("officer", "officer", "someone-else"):
        case = await repository.create(CaseCreate(title="Synthetic case", description="Test narrative"), owner)
        case_ids.append(case.id)
    a, b, hidden = case_ids
    alerts = [{"id": "visible", "case_ids": [a, b], "severity": "HIGH", "status": "NEW", "title": "Connection",
               "explanation": "Shared synthetic phone", "created_at": "2026-09-04T12:00:00Z"},
              {"id": "hidden", "case_ids": [a, hidden], "severity": "HIGH", "status": "NEW", "title": "Secret connection",
               "explanation": "Must not disclose", "created_at": "2026-09-04T12:00:00Z"}]
    calls = []

    def handle(request):
        calls.append(request.method)
        if offline:
            raise httpx.ConnectError("Graph offline")
        if request.method == "POST":
            return httpx.Response(200, json={"alert": {**alerts[0], "status": "ACKNOWLEDGED"}})
        return httpx.Response(200, json={"alerts": alerts})
    audit = AsyncMock()
    return AlertService(repository, httpx.MockTransport(handle), audit), audit, calls


def test_cross_case_explanation_cannot_leak_a_restricted_case():
    async def exercise():
        service, _, _ = await scoped_service()
        result = await service.list(user())
        assert result.total == result.unread == 1
        assert [item.id for item in result.items] == ["visible"]
        assert "Must not disclose" not in result.model_dump_json()
    asyncio.run(exercise())


def test_alert_outage_is_not_an_empty_success():
    async def exercise():
        service, _, _ = await scoped_service(offline=True)
        with pytest.raises(HTTPException) as caught:
            await service.list(user())
        assert caught.value.status_code == 503
    asyncio.run(exercise())


def test_acknowledgement_requires_scope_and_durable_audit():
    async def exercise():
        service, audit, calls = await scoped_service()
        with pytest.raises(HTTPException) as caught:
            await service.acknowledge("hidden", user())
        assert caught.value.status_code == 404
        assert "POST" not in calls
        result = await service.acknowledge("visible", user())
        assert result.status == "ACKNOWLEDGED"
        assert [call.args[2] for call in audit.await_args_list] == ["ALERT_ACK_REQUESTED", "ALERT_ACKNOWLEDGED"]
    asyncio.run(exercise())


def test_analyst_cannot_acknowledge_alerts():
    async def exercise():
        service, audit, calls = await scoped_service()
        with pytest.raises(HTTPException) as caught:
            await service.acknowledge("visible", user("ANALYST"))
        assert caught.value.status_code == 403
        assert not calls
        audit.assert_not_called()
    asyncio.run(exercise())
