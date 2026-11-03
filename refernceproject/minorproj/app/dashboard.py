"""
Streamlit Dashboard for OCEANWATCH
Interactive web interface for marine plastic pollution analysis
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import requests
import json
from datetime import datetime
import os

# Page configuration
st.set_page_config(
    page_title="OCEANWATCH - Marine Plastic Pollution Intelligence",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #1e88e5;
        text-align: center;
        margin-bottom: 2rem;
    }
    .metric-card {
        background-color: #f0f8ff;
        padding: 1rem;
        border-radius: 0.5rem;
        margin: 0.5rem 0;
    }
    .info-box {
        background-color: #e3f2fd;
        padding: 1rem;
        border-radius: 0.5rem;
        border-left: 4px solid #1e88e5;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# API Configuration
API_BASE_URL = "http://localhost:8000"

def fetch_api_data(endpoint: str) -> dict:
    """Fetch data from the API"""
    try:
        response = requests.get(f"{API_BASE_URL}{endpoint}")
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching data from API: {e}")
        return None

def create_pollution_map(data: pd.DataFrame) -> folium.Map:
    """Create an interactive map showing pollution locations"""
    # Create base map centered on mean coordinates
    m = folium.Map(
        location=[data['Latitude'].mean(), data['Longitude'].mean()],
        zoom_start=2,
        tiles='OpenStreetMap'
    )
    
    # Add markers for pollution points
    for idx, row in data.iterrows():
        # Color based on pollution weight
        if row['Plastic_Weight_kg'] > data['Plastic_Weight_kg'].quantile(0.75):
            color = 'red'
        elif row['Plastic_Weight_kg'] > data['Plastic_Weight_kg'].quantile(0.5):
            color = 'orange'
        else:
            color = 'green'
        
        folium.CircleMarker(
            location=[row['Latitude'], row['Longitude']],
            radius=5,
            popup=f"Region: {row['Region']}<br>Plastic: {row['Plastic_Type']}<br>Weight: {row['Plastic_Weight_kg']:.2f} kg",
            color=color,
            fill=True,
            fillColor=color,
            fillOpacity=0.6
        ).add_to(m)
    
    return m

def main():
    """Main dashboard application"""
    
    # Header
    st.markdown('<div class="main-header">🌊 OCEANWATCH</div>', unsafe_allow_html=True)
    st.markdown('<p style="text-align: center; font-size: 1.2rem;">Marine Plastic Pollution Intelligence System</p>', unsafe_allow_html=True)
    
    # Sidebar
    st.sidebar.title("Navigation")
    page = st.sidebar.radio("Select Page", [
        "Dashboard Overview",
        "Hotspot Analysis",
        "Pollution Forecasting",
        "Cleanup Priorities",
        "Model Performance"
    ])
    
    # Sidebar filters
    st.sidebar.title("Filters")
    
    # Fetch regions and plastic types
    regions_data = fetch_api_data("/api/data/regions")
    plastic_types_data = fetch_api_data("/api/data/plastic-types")
    
    if regions_data and plastic_types_data:
        regions = regions_data.get('regions', [])
        plastic_types = plastic_types_data.get('plastic_types', [])
        
        selected_region = st.sidebar.selectbox("Select Region", ["All Regions"] + regions)
        selected_plastic = st.sidebar.selectbox("Select Plastic Type", ["All Types"] + plastic_types)
    else:
        selected_region = "All Regions"
        selected_plastic = "All Types"
    
    # Page content
    if page == "Dashboard Overview":
        st.header("📊 Dashboard Overview")
        
        # Fetch summary data
        summary_data = fetch_api_data("/api/data/summary")
        
        if summary_data:
            # Key metrics
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Total Records", f"{summary_data['total_records']:,}")
            
            with col2:
                st.metric("Total Pollution", f"{summary_data['total_pollution_kg']:,.0f} kg")
            
            with col3:
                st.metric("Avg Pollution", f"{summary_data['avg_pollution_kg']:.1f} kg")
            
            with col4:
                st.metric("Regions Monitored", len(summary_data['regions']))
            
            # Date range
            st.info(f"📅 Data Range: {summary_data['date_range']['start']} to {summary_data['date_range']['end']}")
            
            # Load processed data for visualizations
            if os.path.exists('data/processed/ocean_plastic_pollution_processed.csv'):
                data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
                
                # Apply filters
                if selected_region != "All Regions":
                    data = data[data['Region'] == selected_region]
                if selected_plastic != "All Types":
                    data = data[data['Plastic_Type'] == selected_plastic]
                
                if len(data) > 0:
                    # Create tabs for different views
                    tab1, tab2, tab3 = st.tabs(["🗺️ Geographic View", "📈 Temporal Trends", "🥊 Plastic Distribution"])
                    
                    with tab1:
                        st.subheader("Geographic Distribution")
                        pollution_map = create_pollution_map(data)
                        st_folium(pollution_map, width=1200, height=500)
                    
                    with tab2:
                        st.subheader("Pollution Over Time")
                        data['Date'] = pd.to_datetime(data['Date'])
                        daily_data = data.groupby(data['Date'].dt.date).agg({
                            'Plastic_Weight_kg': 'sum'
                        }).reset_index()
                        
                        fig = px.line(daily_data, x='Date', y='Plastic_Weight_kg',
                                     title='Daily Plastic Pollution Over Time',
                                     labels={'Plastic_Weight_kg': 'Plastic Weight (kg)', 'Date': 'Date'})
                        st.plotly_chart(fig, use_container_width=True)
                    
                    with tab3:
                        st.subheader("Plastic Type Distribution")
                        plastic_counts = data['Plastic_Type'].value_counts()
                        fig = px.pie(values=plastic_counts.values, names=plastic_counts.index,
                                     title='Distribution of Plastic Types')
                        st.plotly_chart(fig, use_container_width=True)
                else:
                    st.warning("No data available for the selected filters.")
            else:
                st.error("Processed data not found. Please run the data processing pipeline first.")
    
    elif page == "Hotspot Analysis":
        st.header("🎯 Hotspot Analysis")
        
        # Fetch hotspot data
        hotspot_data = fetch_api_data("/api/hotspots")
        
        if hotspot_data:
            st.info(f"🎯 Total Hotspots Detected: {hotspot_data['total_hotspots']}")
            
            # Display hotspots table
            hotspots_df = pd.DataFrame(hotspot_data['hotspots'])
            
            if len(hotspots_df) > 0:
                # Top hotspots
                st.subheader("Top Pollution Hotspots")
                top_hotspots = hotspots_df.nlargest(10, 'Hotspot_Intensity_Score')
                
                fig = px.bar(top_hotspots, x='Cluster', y='Hotspot_Intensity_Score',
                            color='Region',
                            title='Top 10 Pollution Hotspots by Intensity Score',
                            labels={'Hotspot_Intensity_Score': 'Intensity Score', 'Cluster': 'Hotspot ID'})
                st.plotly_chart(fig, use_container_width=True)
                
                # Hotspot details table
                st.subheader("Hotspot Details")
                display_columns = ['Cluster', 'Region', 'Hotspot_Intensity_Score', 
                                  'Plastic_Weight_kg_sum', 'Cluster_Area_km2']
                st.dataframe(top_hotspots[display_columns])
                
                # Hotspot map
                st.subheader("Geographic Distribution of Hotspots")
                if 'Latitude_mean' in hotspots_df.columns and 'Longitude_mean' in hotspots_df.columns:
                    hotspot_map = folium.Map(
                        location=[hotspots_df['Latitude_mean'].mean(), hotspots_df['Longitude_mean'].mean()],
                        zoom_start=2
                    )
                    
                    for idx, row in hotspots_df.iterrows():
                        folium.CircleMarker(
                            location=[row['Latitude_mean'], row['Longitude_mean']],
                            radius=row['Hotspot_Intensity_Score'] / 10,
                            popup=f"Hotspot {row['Cluster']}<br>Region: {row['Region']}<br>Intensity: {row['Hotspot_Intensity_Score']:.1f}",
                            color='red',
                            fill=True,
                            fillColor='red',
                            fillOpacity=0.6
                        ).add_to(hotspot_map)
                    
                    st_folium(hotspot_map, width=1200, height=500)
            else:
                st.warning("No hotspots detected.")
        else:
            st.error("Unable to fetch hotspot data. Make sure the hotspot detection model has been trained.")
    
    elif page == "Pollution Forecasting":
        st.header("🔮 Pollution Forecasting")
        
        # Fetch forecast summary
        forecast_data = fetch_api_data("/api/forecast/summary")
        
        if forecast_data:
            st.info(f"🔮 Active Forecasts: {forecast_data['total_forecasts']}")
            
            forecasts_df = pd.DataFrame(forecast_data['forecasts'])
            
            if len(forecasts_df) > 0:
                # Forecast summary table
                st.subheader("Forecast Summary by Region")
                display_columns = ['Group', 'Predicted_Total_Pollution_kg', 'Predicted_Avg_Daily_Pollution_kg',
                                'Trend_Direction', 'MAE', 'RMSE', 'MAPE']
                st.dataframe(forecasts_df[display_columns])
                
                # Forecast visualization
                st.subheader("Forecast Comparison")
                fig = px.bar(forecasts_df, x='Group', y='Predicted_Total_Pollution_kg',
                            color='Trend_Direction',
                            title='Predicted Total Pollution by Region (30-Day Forecast)',
                            labels={'Predicted_Total_Pollution_kg': 'Predicted Pollution (kg)', 'Group': 'Region'})
                st.plotly_chart(fig, use_container_width=True)
                
                # Model accuracy metrics
                st.subheader("Model Accuracy Metrics")
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    avg_mae = forecasts_df['MAE'].mean()
                    st.metric("Avg MAE", f"{avg_mae:.2f}")
                
                with col2:
                    avg_rmse = forecasts_df['RMSE'].mean()
                    st.metric("Avg RMSE", f"{avg_rmse:.2f}")
                
                with col3:
                    avg_mape = forecasts_df['MAPE'].mean()
                    st.metric("Avg MAPE", f"{avg_mape:.2f}%")
                
                # Region-specific forecast selector
                st.subheader("Region-Specific Forecast")
                selected_forecast_region = st.selectbox("Select Region for Detailed Forecast", forecasts_df['Group'].tolist())
                
                if selected_forecast_region:
                    region_forecast = forecasts_df[forecasts_df['Group'] == selected_forecast_region].iloc[0]
                    
                    st.info(f"📊 {selected_forecast_region} Forecast Details")
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.metric("Predicted Total (30 days)", f"{region_forecast['Predicted_Total_Pollution_kg']:.0f} kg")
                        st.metric("Avg Daily", f"{region_forecast['Predicted_Avg_Daily_Pollution_kg']:.1f} kg")
                    
                    with col2:
                        st.metric("Trend", region_forecast['Trend_Direction'])
                        st.metric("MAE", f"{region_forecast['MAE']:.2f}")
            else:
                st.warning("No forecast data available.")
        else:
            st.error("Unable to fetch forecast data. Make sure the forecasting model has been trained.")
    
    elif page == "Cleanup Priorities":
        st.header("🚨 Cleanup Priorities")
        
        # Fetch priority summary
        priority_summary = fetch_api_data("/api/priority/summary")
        
        if priority_summary:
            regional_summary = pd.DataFrame(priority_summary['regional_summary'])
            
            st.info(f"🚨 Priority Analysis Available for {priority_summary['total_regions']} Regions")
            
            # Regional priority summary
            st.subheader("Regional Priority Summary")
            fig = px.bar(regional_summary, x='Region', y='Avg_Priority_Score',
                        color='Critical_Count',
                        title='Average Priority Score by Region',
                        labels={'Avg_Priority_Score': 'Avg Priority Score', 'Region': 'Region'},
                        color_continuous_scale='Reds')
            st.plotly_chart(fig, use_container_width=True)
            
            st.dataframe(regional_summary)
            
            # Top cleanup priorities
            st.subheader("Top Cleanup Priorities")
            top_priorities_request = {"region": selected_region if selected_region != "All Regions" else None, "top_n": 20}
            
            try:
                response = requests.post(f"{API_BASE_URL}/api/priority", json=top_priorities_request)
                if response.status_code == 200:
                    top_priorities = response.json()
                    priorities_df = pd.DataFrame(top_priorities['priorities'])
                    
                    if len(priorities_df) > 0:
                        # Priority distribution
                        st.subheader("Priority Category Distribution")
                        priority_counts = priorities_df['Priority_Category'].value_counts()
                        fig = px.pie(values=priority_counts.values, names=priority_counts.index,
                                    title='Distribution of Priority Categories')
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Top priorities table
                        st.subheader("Top 20 Priority Locations")
                        display_columns = ['Region', 'Plastic_Type', 'Plastic_Weight_kg', 'Depth_meters',
                                        'Priority_Score', 'Priority_Category']
                        st.dataframe(priorities_df[display_columns])
                        
                        # Priority score distribution
                        st.subheader("Priority Score Distribution")
                        fig = px.histogram(priorities_df, x='Priority_Score', nbins=20,
                                        title='Distribution of Priority Scores',
                                        labels={'Priority_Score': 'Priority Score'})
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No priority data available for the selected region.")
            except requests.exceptions.RequestException as e:
                st.error(f"Error fetching priority data: {e}")
        else:
            st.error("Unable to fetch priority data. Make sure the priority scoring has been calculated.")
    
    elif page == "Model Performance":
        st.header("📈 Model Performance")
        
        # Fetch model performance data
        performance_data = fetch_api_data("/api/model/performance")
        
        if performance_data:
            st.info("📈 Real ML Model Performance Metrics")
            
            # Hotspot Detection Performance
            if 'hotspot_detection' in performance_data:
                st.subheader("🎯 Hotspot Detection Model")
                hotspot_perf = performance_data['hotspot_detection']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Hotspots Detected", hotspot_perf['total_hotspots'])
                with col2:
                    st.metric("Avg Intensity Score", f"{hotspot_perf['avg_intensity_score']:.1f}")
                with col3:
                    st.metric("Max Intensity Score", f"{hotspot_perf['max_intensity_score']:.1f}")
            
            # Forecasting Performance
            if 'forecasting' in performance_data:
                st.subheader("🔮 Forecasting Model")
                forecast_perf = performance_data['forecasting']
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Forecasts", forecast_perf['total_forecasts'])
                with col2:
                    st.metric("Avg MAE", f"{forecast_perf['avg_mae']:.2f}")
                with col3:
                    st.metric("Avg RMSE", f"{forecast_perf['avg_rmse']:.2f}")
                
                st.metric("Avg MAPE", f"{forecast_perf['avg_mape']:.2f}%")
            
            # Priority Scoring Performance
            if 'priority_scoring' in performance_data:
                st.subheader("🚨 Priority Scoring System")
                priority_perf = performance_data['priority_scoring']
                
                col1, col2, col3, col4 = st.columns(4)
                with col1:
                    st.metric("Locations Analyzed", priority_perf['total_locations'])
                with col2:
                    st.metric("Avg Priority Score", f"{priority_perf['avg_priority_score']:.1f}")
                with col3:
                    st.metric("Critical Priority", priority_perf['critical_count'])
                with col4:
                    st.metric("High Priority", priority_perf['high_count'])
            
            # Model methodology explanation
            st.subheader("📚 Model Methodology")
            
            methodology_expander = st.expander("Hotspot Detection Methodology")
            with methodology_expander:
                st.markdown("""
                **Algorithm:** DBSCAN (Density-Based Spatial Clustering of Applications with Noise)
                
                **Features Used:**
                - Latitude & Longitude (spatial coordinates)
                - Plastic Weight (kg)
                - Depth (meters)
                
                **Evaluation Metrics:**
                - Silhouette Score (cluster quality)
                - Cluster density and area calculations
                - Intensity scoring based on pollution concentration
                
                **Output:** Geographic hotspots with intensity scores and confidence levels
                """)
            
            forecasting_expander = st.expander("Forecasting Methodology")
            with forecasting_expander:
                st.markdown("""
                **Algorithm:** Prophet (Facebook's time-series forecasting library)
                
                **Features Used:**
                - Historical pollution levels by region
                - Temporal patterns (daily, weekly, yearly seasonality)
                - Trend changes and changepoints
                
                **Evaluation Metrics:**
                - Mean Absolute Error (MAE)
                - Root Mean Square Error (RMSE)
                - Mean Absolute Percentage Error (MAPE)
                - Cross-validation with 30-day horizons
                
                **Output:** 30-day pollution forecasts with confidence intervals
                """)
            
            priority_expander = st.expander("Priority Scoring Methodology")
            with priority_expander:
                st.markdown("""
                **Algorithm:** Weighted Multi-Criteria Decision Analysis
                
                **Scoring Components:**
                - Pollution Density (35%): Current pollution level
                - Trend Increase (25%): Future pollution trend
                - Environmental Impact (20%): Depth and ecological factors
                - Plastic Type Risk (15%): Material persistence and toxicity
                - Accessibility (5%): Ease of cleanup operations
                
                **Output:** Priority scores (0-100) with categories:
                - Critical (75-100)
                - High (50-75)
                - Medium (25-50)
                - Low (0-25)
                """)
        else:
            st.error("Unable to fetch model performance data. Make sure all models have been trained.")
    
    # Footer
    st.markdown("---")
    st.markdown('<p style="text-align: center; color: gray;">OCEANWATCH - Marine Plastic Pollution Intelligence System | Built with Real ML Models</p>', unsafe_allow_html=True)

if __name__ == "__main__":
    main()
