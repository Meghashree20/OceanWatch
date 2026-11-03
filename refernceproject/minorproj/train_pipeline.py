"""
Complete Training Pipeline for OCEANWATCH
Runs the entire ML pipeline from data processing to model training
"""

import os
import sys
import pandas as pd
import numpy as np
from datetime import datetime

# Add src directory to path
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from data_processing import OceanPlasticDataProcessor
from hotspot_detection import HotspotDetector
from forecasting import PollutionForecaster
from priority_scoring import CleanupPriorityScorer


def print_section(title):
    """Print a formatted section header"""
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60 + "\n")


def main():
    """Run the complete training pipeline"""
    
    print_section("OCEANWATCH - Complete Training Pipeline")
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Step 1: Data Processing
    print_section("Step 1: Data Processing")
    try:
        processor = OceanPlasticDataProcessor('data/raw/ocean_plastic_pollution_data.csv')
        processor.load_data()
        processor.clean_data()
        processor.create_spatial_features()
        
        # Get summary statistics
        stats = processor.get_summary_statistics()
        print("Summary Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Save processed data
        os.makedirs('data/processed', exist_ok=True)
        processor.save_processed_data('data/processed/ocean_plastic_pollution_processed.csv')
        
        # Create aggregated datasets
        daily_region = processor.aggregate_by_region_time('D')
        daily_region.to_csv('data/processed/daily_by_region.csv', index=False)
        
        daily_plastic = processor.aggregate_by_plastic_type_time('D')
        daily_plastic.to_csv('data/processed/daily_by_plastic_type.csv', index=False)
        
        print("Data processing completed successfully")
        
    except Exception as e:
        print(f"Data processing failed: {e}")
        return
    
    # Step 2: Hotspot Detection
    print_section("Step 2: Hotspot Detection")
    try:
        data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
        detector = HotspotDetector(data)
        
        # Detect hotspots
        hotspots_df, hotspot_stats = detector.detect_hotspots_dbscan(eps=0.3, min_samples=5)
        
        # Calculate spatial density
        density = detector.calculate_spatial_density(bandwidth=0.3)
        
        # Evaluate clustering quality
        quality_metrics = detector.evaluate_clustering_quality()
        print("Clustering Quality Metrics:")
        for key, value in quality_metrics.items():
            print(f"  {key}: {value}")
        
        # Get top hotspots
        top_hotspots = detector.get_top_hotspots(10)
        if len(top_hotspots) > 0:
            print(f"\nTop 10 Hotspots:")
            available_columns = [col for col in ['Cluster', 'Region', 'Hotspot_Intensity_Score', 
                               'Plastic_Weight_kg_sum', 'Cluster_Area_km2'] if col in top_hotspots.columns]
            print(top_hotspots[available_columns])
        else:
            print("\nNo significant hotspots detected with current parameters.")
        
        # Save model and results
        os.makedirs('data/models', exist_ok=True)
        detector.save_model('data/models/hotspot_detector.pkl')
        hotspots_df.to_csv('data/processed/hotspots_detected.csv', index=False)
        hotspot_stats.to_csv('data/processed/hotspot_statistics.csv', index=False)
        
        print("Hotspot detection completed successfully")
        
    except Exception as e:
        print(f"Hotspot detection failed: {e}")
        return
    
    # Step 3: Pollution Forecasting
    print_section("Step 3: Pollution Forecasting")
    try:
        data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
        forecaster = PollutionForecaster(data)
        
        # Train models for each region
        forecasts = forecaster.train_all_models(groupby_column='Region', forecast_periods=30)
        
        # Get forecast summary
        summary = forecaster.get_forecast_summary()
        print("\nForecast Summary:")
        print(summary[['Group', 'Predicted_Total_Pollution_kg', 'Trend_Direction', 'MAE', 'RMSE', 'MAPE']])
        
        # Save models
        forecaster.save_models('data/models')
        summary.to_csv('data/processed/forecast_summary.csv', index=False)
        
        print("Pollution forecasting completed successfully")
        
    except Exception as e:
        print(f"Pollution forecasting failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Priority Scoring
    print_section("Step 4: Cleanup Priority Scoring")
    try:
        data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
        hotspot_stats = pd.read_csv('data/processed/hotspot_statistics.csv')
        
        scorer = CleanupPriorityScorer(data, hotspot_stats)
        
        # Calculate priority scores
        priority_df = scorer.calculate_composite_priority_score(data)
        
        # Get top priorities
        top_priorities = scorer.get_priority_rankings(20)
        print("\nTop 20 Cleanup Priorities:")
        print(top_priorities[['Region', 'Plastic_Type', 'Priority_Score', 'Priority_Category']].head(10))
        
        # Get regional summary
        regional_summary = scorer.get_priority_summary_by_region()
        print("\nRegional Priority Summary:")
        print(regional_summary)
        
        # Save results
        scorer.save_priority_scores('data/processed/priority_scores.csv')
        top_priorities.to_csv('data/processed/top_cleanup_priorities.csv', index=False)
        regional_summary.to_csv('data/processed/regional_priority_summary.csv', index=False)
        
        # Save methodology
        import json
        methodology = scorer.get_scoring_methodology()
        with open('data/processed/scoring_methodology.json', 'w') as f:
            json.dump(methodology, f, indent=2)
        
        print("Priority scoring completed successfully")
        
    except Exception as e:
        print(f"Priority scoring failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Final Summary
    print_section("Training Pipeline Complete")
    print(f"Completed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nGenerated Files:")
    print("  data/processed/ocean_plastic_pollution_processed.csv")
    print("  data/processed/hotspots_detected.csv")
    print("  data/processed/hotspot_statistics.csv")
    print("  data/processed/forecast_summary.csv")
    print("  data/processed/priority_scores.csv")
    print("  data/processed/top_cleanup_priorities.csv")
    print("  data/processed/regional_priority_summary.csv")
    print("  data/processed/scoring_methodology.json")
    print("\nTrained Models:")
    print("  data/models/hotspot_detector.pkl")
    print("  data/models/forecast_model_*.pkl")
    print("  data/models/forecasts.pkl")
    print("  data/models/metrics.pkl")
    
    print("\nAll models trained and evaluated successfully!")
    print("You can now start the application with: python run_app.py")


if __name__ == "__main__":
    main()
