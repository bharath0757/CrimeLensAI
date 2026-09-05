"""Tamper-evident audit service with durable storage and authenticated APIs."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.concurrency import run_in_threadpool

from app.api.routes import router
from app.config import Settings
from app.models import HealthResponse
from app.store import ChainCorrupted, EventConflict, LedgerStore

logger = logging.getLogger(__name__)


def create_app(configuration: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application: FastAPI):
        config = configuration or Settings()
        config.validate_runtime()
        store = LedgerStore(config.LEDGER_DATABASE_URL)
        application.state.settings = config
        application.state.store = store
        try:
            if config.LEDGER_AUTO_MIGRATE:
                await run_in_threadpool(store.initialize)
            else:
                await run_in_threadpool(store.assert_ready)
            yield
        finally:
            store.engine.dispose()

    application = FastAPI(
        title="CrimeLensAI Audit Ledger", version="1.0.0", lifespan=lifespan,
        openapi_url="/api/v1/openapi.json", docs_url="/docs", redoc_url=None,
        description="Internal hash-chain audit API. Save checkpoints independently for stronger tamper evidence.",
    )
    application.include_router(router)

    @application.exception_handler(EventConflict)
    async def conflict_handler(_request: Request, _exc: EventConflict):
        return JSONResponse(status_code=409, content={"detail": "Event ID already exists with different data"})

    @application.exception_handler(ChainCorrupted)
    async def integrity_handler(_request: Request, _exc: ChainCorrupted):
        logger.error("Audit ledger integrity failure")
        return JSONResponse(status_code=409, content={"detail": "Ledger integrity failure; append refused"})

    @application.exception_handler(KeyError)
    async def missing_handler(_request: Request, _exc: KeyError):
        return JSONResponse(status_code=404, content={"detail": "Audit record not found"})

    @application.exception_handler(SQLAlchemyError)
    async def database_handler(_request: Request, exc: SQLAlchemyError):
        logger.error("Audit database unavailable: %s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Audit storage unavailable"})

    @application.exception_handler(Exception)
    async def unexpected_handler(_request: Request, exc: Exception):
        logger.error("Unexpected audit service failure: %s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": "Audit operation failed"})

    @application.get("/health", response_model=HealthResponse, include_in_schema=False)
    @application.get("/api/v1/health", response_model=HealthResponse)
    def health(request: Request):
        if not request.app.state.store.healthy():
            return JSONResponse(status_code=503, content={"status": "unhealthy", "service": "ledger"})
        return HealthResponse(status="healthy")

    return application


app = create_app()
