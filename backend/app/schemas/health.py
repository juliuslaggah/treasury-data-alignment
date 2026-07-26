from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Response returned by the API health-check endpoint."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": "healthy",
                "service": "Treasury Data Alignment API",
                "version": "0.1.0",
                "environment": "development",
                "timestamp": "2026-07-15T07:30:00Z",
            }
        }
    )

    status: Literal["healthy"]
    service: str
    version: str
    environment: str
    timestamp: datetime


