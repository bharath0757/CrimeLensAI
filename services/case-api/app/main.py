import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.audit_context import AuditContextMiddleware
from app.core.config import settings
from app.core.exceptions import (
    CrimeLensException,
    crimelens_exception_handler,
    generic_exception_handler,
)
from app.core.health import health_report


@asynccontextmanager
async def lifespan(application: FastAPI):
    worker = None
    task = None
    ingestion_worker = None
    ingestion_task = None
    if settings.DATA_BACKEND == "postgres":
        from app.services.audit_delivery import AuditDelivery
        if not settings.SERVICE_AUTH_TOKEN:
            raise RuntimeError("SERVICE_AUTH_TOKEN is required for durable audit delivery")
        worker = AuditDelivery()
        await asyncio.to_thread(worker.ensure_ready)
        from app.services.ingestion_delivery import IngestionDelivery
        ingestion_worker = IngestionDelivery()
        await asyncio.to_thread(ingestion_worker.ensure_ready)
        task = asyncio.create_task(worker.run(), name="audit-delivery")
        ingestion_task = asyncio.create_task(ingestion_worker.run(), name="ingestion-delivery")
    application.state.audit_delivery_task = task
    application.state.ingestion_delivery_task = ingestion_task
    try:
        yield
    finally:
        if worker:
            worker.stop.set()
        if ingestion_worker:
            ingestion_worker.stop.set()
        if ingestion_task:
            ingestion_task.cancel()
            with suppress(asyncio.CancelledError):
                await ingestion_task
        if task:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)
app.add_middleware(AuditContextMiddleware)

# Configure CORS
origins = list(settings.ALLOWED_ORIGINS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register Exception Handlers
app.add_exception_handler(CrimeLensException, crimelens_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Welcome to CrimeLens AI Backend API. Visit /docs for API documentation.",
        "health": f"{settings.API_V1_STR}/health",
    }


@app.get("/health", summary="Health Check")
async def health_check_alias(request: Request):
    return await health_report(request)
