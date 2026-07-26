from datetime import UTC, datetime

from fastapi import APIRouter, status

from app.core.config import get_settings
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])


@router.get(
    "",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Check API health",
    description="Confirm that the API is running and return service information.",
)
def health_check() -> HealthResponse:
    """Return the current health status of the API."""

    settings = get_settings()

    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        timestamp=datetime.now(UTC),
    )

