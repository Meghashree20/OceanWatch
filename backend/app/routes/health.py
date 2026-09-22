from fastapi import APIRouter
from app.core.config import settings
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str

router = APIRouter()

@router.get("/health", response_model=HealthResponse, summary="Check API health")
async def health_check():
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME
    }
