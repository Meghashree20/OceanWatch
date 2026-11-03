"""
FastAPI Backend for OCEANWATCH
Provides REST API endpoints for the pollution intelligence system
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Optional
import pandas as pd
import numpy as np
import joblib
import os
from datetime import datetime, timedelta

app = FastAPI(
    title="OCEANWATCH API",
    description="Marine Plastic Pollution Intelligence System",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global variables for models and data
data_processor = None
hotspot_detector = None
pollution_forecaster = None
priority_scorer = None


# Pydantic models for API
class LocationRequest(BaseModel):
    latitude: float
    longitude: float
    radius: Optional[float] = 5.0  # radius in km


class ForecastRequest(BaseModel):
    region: str
    plastic_type: Optional[str] = None
    days: Optional[int] = 30


class PriorityRequest(BaseModel):
    region: Optional[str] = None
    top_n: Optional[int] = 20


# Startup event to load models
@app.on_event("startup")
async def startup_event():
    """Load models and data on startup"""
    global data_processor, hotspot_detector, pollution_forecaster, priority_scorer
    
    try:
        # Load processed data
        if os.path.exists('data/processed/ocean_plastic_pollution_processed.csv'):
            data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
            print("Processed data loaded successfully")
        else:
            print("Warning: Processed data not found")
            data = None
        
        # Load hotspot detector
        if os.path.exists('data/models/hotspot_detector.pkl'):
            from hotspot_detection import HotspotDetector
            hotspot_detector = HotspotDetector(data) if data is not None else None
            if hotspot_detector:
                hotspot_detector.load_model('data/models/hotspot_detector.pkl')
                print("Hotspot detector loaded successfully")
        
        # Load pollution forecaster
        if os.path.exists('data/models/forecasts.pkl'):
            from forecasting import PollutionForecaster
            pollution_forecaster = PollutionForecaster(data) if data is not None else None
            if pollution_forecaster:
                pollution_forecaster.load_models('data/models')
                print("Pollution forecaster loaded successfully")
        
        # Load priority scorer
        if os.path.exists('data/processed/priority_scores.csv'):
            from priority_scoring import CleanupPriorityScorer
            priority_scorer = CleanupPriorityScorer(data) if data is not None else None
            if priority_scorer:
                priority_scorer.priority_scores = pd.read_csv('data/processed/priority_scores.csv')
                print("Priority scorer loaded successfully")
        
        print("All models loaded successfully")
        
    except Exception as e:
        print(f"Error loading models: {e}")


# API Endpoints
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "message": "OCEANWATCH - Marine Plastic Pollution Intelligence System",
        "version": "1.0.0",
        "endpoints": {
            "data_summary": "/api/data/summary",
            "hotspots": "/api/hotspots",
            "forecast": "/api/forecast",
            "priority": "/api/priority",
            "regions": "/api/data/regions",
            "plastic_types": "/api/data/plastic-types"
        }
    }


@app.get("/api/data/summary")
async def get_data_summary():
    """Get summary statistics of the dataset"""
    try:
        if not os.path.exists('data/processed/ocean_plastic_pollution_processed.csv'):
            raise HTTPException(status_code=404, detail="Processed data not found")
        
        data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
        
        summary = {
            "total_records": len(data),
            "date_range": {
                "start": data['Date'].min(),
                "end": data['Date'].max()
            },
            "regions": data['Region'].unique().tolist(),
            "plastic_types": data['Plastic_Type'].unique().tolist(),
            "total_pollution_kg": float(data['Plastic_Weight_kg'].sum()),
            "avg_pollution_kg": float(data['Plastic_Weight_kg'].mean()),
            "depth_range": {
                "min": float(data['Depth_meters'].min()),
                "max": float(data['Depth_meters'].max()),
                "avg": float(data['Depth_meters'].mean())
            }
        }
        
        return summary
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/regions")
async def get_regions():
    """Get list of regions in the dataset"""
    try:
        if not os.path.exists('data/processed/ocean_plastic_pollution_processed.csv'):
            raise HTTPException(status_code=404, detail="Processed data not found")
        
        data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
        regions = data['Region'].unique().tolist()
        
        return {"regions": regions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/data/plastic-types")
async def get_plastic_types():
    """Get list of plastic types in the dataset"""
    try:
        if not os.path.exists('data/processed/ocean_plastic_pollution_processed.csv'):
            raise HTTPException(status_code=404, detail="Processed data not found")
        
        data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
        plastic_types = data['Plastic_Type'].unique().tolist()
        
        return {"plastic_types": plastic_types}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hotspots")
async def get_hotspots():
    """Get detected pollution hotspots"""
    try:
        if not os.path.exists('data/processed/hotspot_statistics.csv'):
            raise HTTPException(status_code=404, detail="Hotspot data not found")
        
        hotspot_stats = pd.read_csv('data/processed/hotspot_statistics.csv')
        
        # Convert to list of dictionaries
        hotspots = hotspot_stats.to_dict('records')
        
        return {
            "total_hotspots": len(hotspots),
            "hotspots": hotspots
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hotspots/top")
async def get_top_hotspots(n: int = 10):
    """Get top N hotspots by intensity score"""
    try:
        if not os.path.exists('data/processed/hotspot_statistics.csv'):
            raise HTTPException(status_code=404, detail="Hotspot data not found")
        
        hotspot_stats = pd.read_csv('data/processed/hotspot_statistics.csv')
        top_hotspots = hotspot_stats.nlargest(n, 'Hotspot_Intensity_Score')
        
        return {
            "top_n": n,
            "hotspots": top_hotspots.to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/forecast")
async def get_forecast(request: ForecastRequest):
    """Get pollution forecast for a specific region"""
    try:
        if not os.path.exists('data/processed/forecast_summary.csv'):
            raise HTTPException(status_code=404, detail="Forecast data not found")
        
        forecast_summary = pd.read_csv('data/processed/forecast_summary.csv')
        
        # Filter by region if specified
        if request.region:
            forecast_data = forecast_summary[forecast_summary['Group'] == request.region]
            if len(forecast_data) == 0:
                raise HTTPException(status_code=404, detail=f"No forecast found for region: {request.region}")
        else:
            forecast_data = forecast_summary
        
        return {
            "region": request.region,
            "forecast_period_days": request.days,
            "forecasts": forecast_data.to_dict('records')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/forecast/summary")
async def get_forecast_summary():
    """Get summary of all forecasts"""
    try:
        if not os.path.exists('data/processed/forecast_summary.csv'):
            raise HTTPException(status_code=404, detail="Forecast summary not found")
        
        forecast_summary = pd.read_csv('data/processed/forecast_summary.csv')
        
        return {
            "total_forecasts": len(forecast_summary),
            "forecasts": forecast_summary.to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/priority")
async def get_priority_rankings(request: PriorityRequest):
    """Get cleanup priority rankings"""
    try:
        if not os.path.exists('data/processed/top_cleanup_priorities.csv'):
            raise HTTPException(status_code=404, detail="Priority data not found")
        
        priorities = pd.read_csv('data/processed/top_cleanup_priorities.csv')
        
        # Filter by region if specified
        if request.region:
            priorities = priorities[priorities['Region'] == request.region]
            if len(priorities) == 0:
                raise HTTPException(status_code=404, detail=f"No priorities found for region: {request.region}")
        
        # Get top N
        top_priorities = priorities.head(request.top_n)
        
        return {
            "region": request.region,
            "top_n": request.top_n,
            "priorities": top_priorities.to_dict('records')
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/priority/summary")
async def get_priority_summary():
    """Get priority summary by region"""
    try:
        if not os.path.exists('data/processed/regional_priority_summary.csv'):
            raise HTTPException(status_code=404, detail="Regional priority summary not found")
        
        regional_summary = pd.read_csv('data/processed/regional_priority_summary.csv')
        
        return {
            "total_regions": len(regional_summary),
            "regional_summary": regional_summary.to_dict('records')
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/model/performance")
async def get_model_performance():
    """Get model performance metrics"""
    try:
        performance_data = {}
        
        # Hotspot detection metrics
        if os.path.exists('data/processed/hotspot_statistics.csv'):
            hotspot_stats = pd.read_csv('data/processed/hotspot_statistics.csv')
            performance_data['hotspot_detection'] = {
                "total_hotspots": len(hotspot_stats),
                "avg_intensity_score": float(hotspot_stats['Hotspot_Intensity_Score'].mean()),
                "max_intensity_score": float(hotspot_stats['Hotspot_Intensity_Score'].max())
            }
        
        # Forecasting metrics
        if os.path.exists('data/processed/forecast_summary.csv'):
            forecast_summary = pd.read_csv('data/processed/forecast_summary.csv')
            performance_data['forecasting'] = {
                "total_forecasts": len(forecast_summary),
                "avg_mae": float(forecast_summary['MAE'].mean()),
                "avg_rmse": float(forecast_summary['RMSE'].mean()),
                "avg_mape": float(forecast_summary['MAPE'].mean())
            }
        
        # Priority scoring metrics
        if os.path.exists('data/processed/priority_scores.csv'):
            priority_scores = pd.read_csv('data/processed/priority_scores.csv')
            performance_data['priority_scoring'] = {
                "total_locations": len(priority_scores),
                "avg_priority_score": float(priority_scores['Priority_Score'].mean()),
                "critical_count": int((priority_scores['Priority_Category'] == 'Critical').sum()),
                "high_count": int((priority_scores['Priority_Category'] == 'High').sum())
            }
        
        return performance_data
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
