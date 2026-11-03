# OCEANWATCH - Marine Plastic Pollution Intelligence System

A complete, realistic, end-to-end AIML application that analyzes marine plastic pollution data, detects pollution hotspots, forecasts future pollution levels, and recommends cleanup priority locations.

## 🎯 Project Overview

OCEANWATCH answers three critical questions about marine plastic pollution:

1. **WHERE** is marine plastic pollution concentrated? → Geospatial hotspot detection
2. **HOW** is pollution likely to change? → Time-series pollution forecasting  
3. **WHERE** should cleanup efforts be prioritized? → Data-driven cleanup priority recommendation

## ✨ Key Features

- **Real ML Models**: All predictions come from actually trained/evaluated models
- **Interactive Dashboard**: Streamlit-based web interface for data exploration
- **Geospatial Analysis**: DBSCAN clustering for hotspot detection
- **Time-Series Forecasting**: Prophet-based pollution level predictions
- **Priority Scoring**: Multi-criteria decision analysis for cleanup recommendations
- **REST API**: FastAPI backend for model serving
- **Comprehensive Documentation**: Complete ML methodology and evaluation metrics

## 📊 Dataset

- **Source**: Kaggle - Ocean Plastic Pollution Dataset
- **Size**: 15,000 hourly records (January - December 2015)
- **Coverage**: 5 ocean regions (Arctic, Southern, Indian, Atlantic, Pacific)
- **Features**: Date, Region, Latitude, Longitude, Plastic Type, Weight, Depth

## 🏗️ Architecture

```
oceanwatch/
├── data/
│   ├── raw/                    # Original dataset
│   ├── processed/              # Cleaned and engineered data
│   └── models/                 # Trained model artifacts
├── src/
│   ├── data_processing.py      # Data cleaning and feature engineering
│   ├── hotspot_detection.py   # Geospatial clustering model
│   ├── forecasting.py         # Time-series forecasting model
│   ├── priority_scoring.py     # Cleanup priority algorithm
│   └── api.py                  # FastAPI backend
├── app/
│   └── dashboard.py            # Streamlit dashboard
├── notebooks/                  # Jupyter notebooks for analysis
├── tests/                      # Model tests
├── requirements.txt            # Python dependencies
└── README.md                   # This file
```

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- pip package manager

### Installation

1. Clone the repository:
```bash
git clone <repository-url>
cd oceanwatch
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Download the dataset:
```bash
python dataset.py
```

### Running the Complete Pipeline

Run the entire ML pipeline (data processing → model training → evaluation):

```bash
python train_pipeline.py
```

This will:
1. Process and clean the data
2. Train hotspot detection model
3. Train forecasting models
4. Calculate cleanup priority scores
5. Evaluate all models
6. Save trained models and results

### Starting the Application

**Option 1: Start API and Dashboard separately**

1. Start the FastAPI backend:
```bash
python src/api.py
```

2. In a new terminal, start the Streamlit dashboard:
```bash
streamlit run app/dashboard.py
```

**Option 2: Start everything with run_app.py**

```bash
python run_app.py
```

Then open your browser to `http://localhost:8501`

## 📈 ML Models

### 1. Hotspot Detection (DBSCAN Clustering)

**Algorithm**: Density-Based Spatial Clustering of Applications with Noise

**Features**: Latitude, Longitude, Plastic Weight, Depth

**Output**: Geographic hotspots with intensity scores

**Evaluation Metrics**:
- Silhouette Score (cluster quality)
- Cluster density analysis
- Spatial density estimation

### 2. Pollution Forecasting (Prophet)

**Algorithm**: Facebook Prophet time-series forecasting

**Features**: Historical pollution data by region

**Output**: 30-day pollution forecasts with confidence intervals

**Evaluation Metrics**:
- Mean Absolute Error (MAE)
- Root Mean Square Error (RMSE)
- Mean Absolute Percentage Error (MAPE)
- Cross-validation with 30-day horizons

### 3. Cleanup Priority Scoring

**Algorithm**: Weighted Multi-Criteria Decision Analysis

**Components**:
- Pollution Density (35%)
- Trend Increase (25%)
- Environmental Impact (20%)
- Plastic Type Risk (15%)
- Accessibility (5%)

**Output**: Priority scores (0-100) with categories (Critical, High, Medium, Low)

## 📱 Dashboard Features

- **Dashboard Overview**: Key metrics, geographic distribution, temporal trends
- **Hotspot Analysis**: Interactive hotspot map, intensity rankings
- **Pollution Forecasting**: Regional forecasts, model accuracy metrics
- **Cleanup Priorities**: Priority rankings, regional summary
- **Model Performance**: Real ML model metrics and methodology

## 🔧 API Endpoints

- `GET /api/data/summary` - Dataset summary statistics
- `GET /api/hotspots` - Detected pollution hotspots
- `POST /api/forecast` - Get pollution forecast for region
- `POST /api/priority` - Get cleanup priority rankings
- `GET /api/model/performance` - Model performance metrics

## 🧪 Testing

Run the test suite:

```bash
pytest tests/
```

## 📚 Documentation

- **Project Architecture**: See `PROJECT_ARCHITECTURE.md`
- **Model Documentation**: See `MODEL_DOCUMENTATION.md` (comprehensive ML methodology and results)
- **API Documentation**: Available at `http://localhost:8000/docs` when API is running
- **Scoring Methodology**: See `data/processed/scoring_methodology.json` (after training)

## 🎓 Learning Outcomes

This project demonstrates:
- Real-world ML pipeline development
- Geospatial data analysis and clustering
- Time-series forecasting with Prophet
- Multi-criteria decision analysis
- Full-stack web application development
- Model evaluation and validation
- Interactive data visualization

## 🤝 Contributing

This is a student minor project. Contributions and suggestions are welcome!

## 📝 License

This project is for educational purposes.

## 🙏 Acknowledgments

- Dataset: Kaggle - Ocean Plastic Pollution Dataset
- ML Libraries: Scikit-learn, Prophet, Streamlit, FastAPI
- Inspiration: Marine conservation and environmental protection

---

**Built with real ML models and actual data - no fake results!**

🌊 **OCEANWATCH - Protecting Our Oceans with Data Science** 🌊
