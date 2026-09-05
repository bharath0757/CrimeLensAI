"""Shared readiness checks for the gateway's health routes."""

import asyncio

from fastapi import HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.core.config import settings


async def health_report(request: Request) -> dict:
    if settings.DATA_BACKEND == "postgres":
        from app.repositories.postgres import get_engine

        def check_database():
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1")).scalar_one()

        try:
            await asyncio.to_thread(check_database)
        except SQLAlchemyError as exc:
            raise HTTPException(status_code=503, detail="Database unavailable") from exc
        worker = getattr(request.app.state, "audit_delivery_task", None)
        if worker is None or worker.done():
            raise HTTPException(status_code=503, detail="Audit delivery worker unavailable")
        ingestion_worker = getattr(request.app.state, "ingestion_delivery_task", None)
        if ingestion_worker is None or ingestion_worker.done():
            raise HTTPException(status_code=503, detail="Structured ingestion worker unavailable")
    return {
        "status": "healthy", "app": settings.PROJECT_NAME, "version": settings.VERSION,
        "message": "CrimeLens AI backend is operating normally.",
        "data_backend": settings.DATA_BACKEND,
        "audit_delivery": "running" if settings.DATA_BACKEND == "postgres" else "disabled-development",
    }
