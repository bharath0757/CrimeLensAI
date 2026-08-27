from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exceptions import CrimeLensException, crimelens_exception_handler, generic_exception_handler

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Configure CORS
if settings.ALLOWED_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
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
async def health_check_alias():
    return {
        "status": "healthy",
        "message": "CrimeLens AI backend is operating normally.",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
