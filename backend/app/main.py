from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.logging_config import logger
from app.db.mongodb import connect_to_mongo, close_mongo_connection
from app.db.indexes import create_indexes
from app.routes import health, data, hotspots, forecast, recommendations


OPENAPI_TAGS = [
    {"name": "System", "description": "Service health and operational endpoints."},
    {"name": "Data", "description": "NOAA observation import, search, and statistics."},
    {"name": "Hotspots", "description": "Pollution hotspot detection and cluster queries."},
    {"name": "Forecasting", "description": "Model-based pollution concentration forecasts."},
    {"name": "Recommendations", "description": "Transparent cleanup priority recommendations."},
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await connect_to_mongo()
    await create_indexes()
    yield
    # Shutdown
    await close_mongo_connection()

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="OceanWatch pollution data, hotspot, forecasting, and cleanup recommendation API.",
    version="1.0.0",
    openapi_tags=OPENAPI_TAGS,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# Set up CORS
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Global exception handler
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        headers=exc.headers,
        content={"error": {"code": f"http_{exc.status_code}", "message": str(exc.detail)}},
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={"error": {"code": "validation_error", "message": "Request validation failed", "details": exc.errors()}},
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Global exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "internal_server_error", "message": "Internal server error"}}
    )

# Routers
app.include_router(health.router, prefix="/api", tags=["System"])
app.include_router(data.router, prefix="/api/data", tags=["Data"])
app.include_router(hotspots.router, prefix="/api/hotspots", tags=["Hotspots"])
app.include_router(forecast.router, prefix="/api/forecast", tags=["Forecasting"])
app.include_router(recommendations.router, prefix="/api/recommendations", tags=["Recommendations"])
