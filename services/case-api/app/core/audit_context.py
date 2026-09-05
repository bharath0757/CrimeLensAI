"""Request-local attribution propagated into PostgreSQL transactions."""

from contextvars import ContextVar
from uuid import uuid4

audit_actor: ContextVar[str] = ContextVar("audit_actor", default="system:case-api")
audit_request_id: ContextVar[str] = ContextVar("audit_request_id", default="")


class AuditContextMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        # Generate the ID server-side; never trust an inbound actor/request identity.
        actor_token = audit_actor.set("anonymous")
        request_token = audit_request_id.set(str(uuid4()))
        try:
            await self.app(scope, receive, send)
        finally:
            audit_actor.reset(actor_token)
            audit_request_id.reset(request_token)
