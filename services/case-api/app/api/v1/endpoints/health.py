from fastapi import APIRouter
from app.core.config import settings

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check():
    """
    Returns application health status.
    """
    return {
        "status": "healthy",
        "message": "CrimeLens AI backend is operating normally.",
        "app": settings.PROJECT_NAME,
        "version": settings.VERSION,
    }
