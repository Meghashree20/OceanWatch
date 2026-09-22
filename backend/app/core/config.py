from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Union

class Settings(BaseSettings):
    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env")

    PROJECT_NAME: str = "OceanWatch API"
    API_V1_STR: str = "/api/v1"
    
    # MongoDB
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "oceanwatch"
    MONGODB_SERVER_SELECTION_TIMEOUT_MS: int = 5000
    MONGODB_CONNECT_TIMEOUT_MS: int = 5000

    DBSCAN_EPS_KM: float = 150.0
    DBSCAN_MIN_SAMPLES: int = 10
    
    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173", "http://localhost:8000"]
    
settings = Settings()
