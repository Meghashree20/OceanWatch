
from fastapi import APIRouter, HTTPException, Request
from app.core.config import settings
from app.db.mongodb import db_client
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


router = APIRouter()


@router.get("/health", response_model=HealthResponse, summary="Check API health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
    }


@router.get("/ready", response_model=HealthResponse, summary="Check API and database readiness")
async def readiness_check(request: Request):
    if not getattr(request.app.state, "startup_ready", False) or db_client.client is None:
        raise HTTPException(status_code=503, detail="Service dependencies are not ready.")
    try:
        await db_client.client.admin.command("ping")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database readiness check failed.") from exc
    return {
        "status": "ready",
        "service": settings.PROJECT_NAME,
    }
