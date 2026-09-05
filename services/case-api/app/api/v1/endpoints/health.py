from fastapi import APIRouter, Request

from app.core.health import health_report

router = APIRouter()


@router.get("/health", summary="Health Check")
async def health_check(request: Request):
    """
    Returns application health status.
    """
    return await health_report(request)
