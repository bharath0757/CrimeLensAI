from fastapi import Request, status
from fastapi.responses import JSONResponse


class CrimeLensException(Exception):
    """Base exception class for CrimeLens AI Backend."""

    def __init__(self, message: str, status_code: int = status.HTTP_400_BAD_REQUEST):
        self.message = message
        self.status_code = status_code
        super().__init__(self.message)


async def crimelens_exception_handler(request: Request, exc: CrimeLensException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "message": exc.message,
                "status_code": exc.status_code,
            },
        },
    )


async def generic_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "message": "An unexpected server error occurred.",
                "status_code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            },
        },
    )
