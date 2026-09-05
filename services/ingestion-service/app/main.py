import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router


@asynccontextmanager
async def lifespan(_application: FastAPI):
    if os.getenv("ENVIRONMENT", "development").lower() == "production" and len(
        os.getenv("SERVICE_AUTH_TOKEN", "").encode()
    ) < 32:
        raise RuntimeError("Production ingestion service requires a 32-byte service token")
    yield


app = FastAPI(
    title="CrimeLensAI - Ingestion Service",
    version="0.1.0",
    lifespan=lifespan,
)
app.include_router(router)

@app.get("/health", tags=["Health"])
async def health_check():
    return {"status": "healthy", "service": "ingestion", "version": "0.1.0"}
