"""Health check endpoint."""
from fastapi import APIRouter

from app.database import mongo_manager
from app.schemas.common import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Returns service status and, optionally, MongoDB connectivity.",
)
async def health_check() -> HealthResponse:
    db_status = None
    if mongo_manager.client is not None:
        try:
            await mongo_manager.client.admin.command("ping")
            db_status = "connected"
        except Exception:
            db_status = "disconnected"

    return HealthResponse(status="ok", database=db_status)
