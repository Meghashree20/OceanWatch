# OCEANWATCH - Usage Guide

## Quick Start

### 1. Installation
```bash
# Install dependencies
pip install -r requirements.txt

# Download dataset
python dataset.py
```

### 2. Train Models
```bash
# Run complete training pipeline
python train_pipeline.py
```

This will:
- Process and clean the data
- Train hotspot detection model
- Train forecasting models for all regions
- Calculate cleanup priority scores
- Save all models and results

### 3. Start Application
```bash
# Start both API and dashboard
python run_app.py
```

Or start separately:
```bash
# Terminal 1: Start API
python src/api.py

# Terminal 2: Start Dashboard
streamlit run app/dashboard.py
```

### 4. Access Application
- **Dashboard:** http://localhost:8501
- **API:** http://localhost:8000
- **API Documentation:** http://localhost:8000/docs

---

## Dashboard Guide

### Dashboard Overview
- **Key Metrics:** Total records, pollution amounts, regional statistics
- **Geographic View:** Interactive map showing pollution locations
- **Temporal Trends:** Daily pollution over time
- **Plastic Distribution:** Pie chart of plastic types

### Hotspot Analysis
- **Top Hotspots:** Bar chart of most intense pollution areas
- **Hotspot Details:** Table with cluster information
- **Geographic Distribution:** Map of detected hotspots
- **Intensity Scores:** Ranking by pollution concentration

### Pollution Forecasting
- **Forecast Summary:** Regional predictions for 30 days
- **Model Accuracy:** MAE, RMSE, MAPE metrics
- **Trend Analysis:** Increasing/decreasing pollution trends
- **Regional Forecasts:** Detailed predictions per region

### Cleanup Priorities
- **Regional Summary:** Priority scores by region
- **Top Priorities:** Highest ranked cleanup locations
- **Priority Distribution:** Category breakdown (Critical, High, Medium, Low)
- **Score Analysis:** Distribution of priority scores

### Model Performance
- **Hotspot Detection:** Clustering quality metrics
- **Forecasting:** Accuracy metrics and evaluation
- **Priority Scoring:** Score distribution and counts
- **Methodology:** Detailed explanation of each model

---

## API Guide

### Endpoints

#### Data Endpoints
- `GET /api/data/summary` - Dataset summary statistics
- `GET /api/data/regions` - List of available regions
- `GET /api/data/plastic-types` - List of plastic types

#### Hotspot Endpoints
- `GET /api/hotspots` - All detected hotspots
- `GET /api/hotspots/top?n=10` - Top N hotspots

#### Forecast Endpoints
- `POST /api/forecast` - Get forecast for specific region
  ```json
  {
    "region": "Arctic Ocean",
    "plastic_type": null,
    "days": 30
  }
  ```
- `GET /api/forecast/summary` - All forecast summaries

#### Priority Endpoints
- `POST /api/priority` - Get priority rankings
  ```json
  {
    "region": "Arctic Ocean",
    "top_n": 20
  }
  ```
- `GET /api/priority/summary` - Regional priority summary

#### Performance Endpoints
- `GET /api/model/performance` - All model performance metrics

### Example API Usage

```python
import requests

# Get data summary
response = requests.get('http://localhost:8000/api/data/summary')
data = response.json()
print(f"Total records: {data['total_records']}")

# Get top hotspots
response = requests.get('http://localhost:8000/api/hotspots/top?n=5')
hotspots = response.json()
print(f"Top {hotspots['top_n']} hotspots: {hotspots['hotspots']}")

# Get forecast for Arctic Ocean
forecast_request = {
    "region": "Arctic Ocean",
    "days": 30
}
response = requests.post('http://localhost:8000/api/forecast', json=forecast_request)
forecast = response.json()
print(f"Arctic Ocean forecast: {forecast}")

# Get cleanup priorities
priority_request = {
    "region": "Pacific Ocean",
    "top_n": 10
}
response = requests.post('http://localhost:8000/api/priority', json=priority_request)
priorities = response.json()
print(f"Top priorities: {priorities['priorities']}")
```

---

## Model Training Guide

### Individual Model Training

#### Data Processing Only
```python
from src.data_processing import OceanPlasticDataProcessor

processor = OceanPlasticDataProcessor('data/raw/ocean_plastic_pollution_data.csv')
processor.load_data()
processor.clean_data()
processor.create_spatial_features()
processor.save_processed_data('data/processed/processed_data.csv')
```

#### Hotspot Detection Only
```python
from src.hotspot_detection import HotspotDetector
import pandas as pd

data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
detector = HotspotDetector(data)
hotspots_df, hotspot_stats = detector.detect_hotspots_dbscan(eps=0.3, min_samples=5)
detector.save_model('data/models/hotspot_detector.pkl')
```

#### Forecasting Only
```python
from src.forecasting import PollutionForecaster
import pandas as pd

data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
forecaster = PollutionForecaster(data)
forecasts = forecaster.train_all_models(groupby_column='Region', forecast_periods=30)
forecaster.save_models('data/models')
```

#### Priority Scoring Only
```python
from src.priority_scoring import CleanupPriorityScorer
import pandas as pd

data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
scorer = CleanupPriorityScorer(data)
priority_df = scorer.calculate_composite_priority_score(data)
scorer.save_priority_scores('data/processed/priority_scores.csv')
```

### Custom Parameters

#### Adjust Hotspot Detection
```python
# More sensitive detection (more clusters)
hotspots_df, stats = detector.detect_hotspots_dbscan(eps=0.2, min_samples=3)

# Less sensitive detection (fewer, larger clusters)
hotspots_df, stats = detector.detect_hotspots_dbscan(eps=0.5, min_samples=10)
```

#### Adjust Forecasting
```python
# Longer forecast horizon
forecasts = forecaster.train_all_models(forecast_periods=60)

# Different grouping
forecasts = forecaster.train_all_models(groupby_column='Plastic_Type')
```

#### Adjust Priority Scoring
```python
# Custom weights
new_weights = {
    'pollution_density': 0.40,
    'trend_increase': 0.20,
    'environmental_impact': 0.25,
    'plastic_type_risk': 0.10,
    'accessibility': 0.05
}
scorer.update_scoring_weights(new_weights)
```

---

## File Structure

```
oceanwatch/
├── data/
│   ├── raw/
│   │   └── ocean_plastic_pollution_data.csv      # Original dataset
│   ├── processed/
│   │   ├── ocean_plastic_pollution_processed.csv # Cleaned data
│   │   ├── hotspots_detected.csv                 # Hotspot results
│   │   ├── hotspot_statistics.csv                # Hotspot metrics
│   │   ├── forecast_summary.csv                  # Forecast results
│   │   ├── priority_scores.csv                   # Priority scores
│   │   ├── top_cleanup_priorities.csv            # Top priorities
│   │   ├── regional_priority_summary.csv        # Regional summary
│   │   └── scoring_methodology.json              # Scoring documentation
│   └── models/
│       ├── hotspot_detector.pkl                  # Hotspot model
│       ├── forecast_model_*.pkl                  # Prophet models
│       ├── forecasts.pkl                         # Forecast results
│       └── metrics.pkl                           # Performance metrics
├── src/
│   ├── data_processing.py                        # Data cleaning
│   ├── hotspot_detection.py                      # Hotspot detection
│   ├── forecasting.py                            # Time-series forecasting
│   ├── priority_scoring.py                      # Priority scoring
│   └── api.py                                    # FastAPI backend
├── app/
│   └── dashboard.py                              # Streamlit dashboard
├── dataset.py                                    # Dataset download
├── train_pipeline.py                             # Complete training
├── run_app.py                                    # Application launcher
├── requirements.txt                              # Dependencies
├── README.md                                     # Project overview
├── PROJECT_ARCHITECTURE.md                       # Architecture details
├── MODEL_DOCUMENTATION.md                        # ML model documentation
└── USAGE_GUIDE.md                                # This file
```

---

## Troubleshooting

### Common Issues

#### ModuleNotFoundError
```bash
# Install missing dependencies
pip install -r requirements.txt
```

#### Data Not Found
```bash
# Download dataset first
python dataset.py
```

#### API Connection Failed
```bash
# Check if API is running
curl http://localhost:8000/api/data/summary

# Start API manually
python src/api.py
```

#### Dashboard Not Loading
```bash
# Check if API is running first
# Then start dashboard
streamlit run app/dashboard.py
```

#### Prophet Training Warnings
- **"Yearly seasonality is enabled with less than 730 days"**: This is expected with 1 year of data. The model will still work but with higher uncertainty.
- **"Seasonality has period larger than initial window"**: Also expected with limited data. Consider reducing forecast horizon.

#### Memory Issues
```python
# Reduce data size for testing
# In data_processing.py, add:
data = data.sample(5000)  # Use subset of data
```

---

## Performance Tips

### Training Performance
- Use SSD for faster I/O
- Reduce dataset size for initial testing
- Parallelize forecasting (Prophet supports parallel processing)
- Cache intermediate results

### API Performance
- Use production WSGI server (Gunicorn) instead of Uvicorn for production
- Implement response caching
- Use database for production instead of CSV files
- Add API rate limiting

### Dashboard Performance
- Reduce data visualization complexity
- Use data sampling for large datasets
- Implement lazy loading for charts
- Optimize Folium map rendering

---

## Extension Ideas

### Additional Features
- **Real-time Data Integration:** Connect to live ocean monitoring systems
- **Historical Comparison:** Compare current pollution levels with historical baselines
- **Impact Assessment:** Environmental impact calculations
- **Cost Estimation:** Cleanup operation cost estimates
- **Team Management:** Assign cleanup teams to priority locations

### Advanced Analytics
- **Drift Modeling:** Predict pollution movement using ocean currents
- **Source Attribution:** Identify potential pollution sources
- **Seasonal Analysis:** Detailed seasonal pattern analysis
- **Correlation Analysis:** Correlate pollution with environmental factors

### Technical Enhancements
- **Database Integration:** PostgreSQL/MySQL for production
- **Authentication:** User authentication and authorization
- **Mobile App:** React Native mobile application
- **Export Functionality:** PDF reports, data exports
- **Alerts System:** Automated pollution alerts

---

## Support and Contributing

### Getting Help
- Check documentation files (README.md, MODEL_DOCUMENTATION.md)
- Review API documentation at http://localhost:8000/docs
- Examine model performance metrics in the dashboard
- Check troubleshooting section above

### Contributing
This is a student minor project. Suggestions for improvement are welcome!

### Reporting Issues
When reporting issues, include:
- Python version
- Error messages
- Steps to reproduce
- System information

---

## Acknowledgments

- **Dataset:** Kaggle - Ocean Plastic Pollution Dataset
- **ML Libraries:** Scikit-learn, Prophet, Streamlit, FastAPI
- **Inspiration:** Marine conservation and environmental protection efforts

---

*Last updated: 2026-09-02*  
*Version: 1.0.0*
