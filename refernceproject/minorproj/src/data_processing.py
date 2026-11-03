"""
Data Processing Module for OCEANWATCH
Handles data cleaning, feature engineering, and preprocessing for ML models
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Tuple
import os


class OceanPlasticDataProcessor:
    """Process ocean plastic pollution data for ML analysis"""
    
    def __init__(self, data_path: str):
        """
        Initialize the data processor
        
        Args:
            data_path: Path to the raw CSV data file
        """
        self.data_path = data_path
        self.raw_data = None
        self.processed_data = None
        
    def load_data(self) -> pd.DataFrame:
        """Load raw data from CSV"""
        self.raw_data = pd.read_csv(self.data_path)
        print(f"Loaded {len(self.raw_data)} records from {self.data_path}")
        return self.raw_data
    
    def clean_data(self) -> pd.DataFrame:
        """
        Clean and preprocess the data
        
        Returns:
            Cleaned DataFrame with proper data types and formatting
        """
        if self.raw_data is None:
            self.load_data()
            
        df = self.raw_data.copy()
        
        # Convert Date to datetime (handle mixed date formats)
        df['Date'] = pd.to_datetime(df['Date'], dayfirst=True, errors='coerce')
        
        # Extract temporal features
        df['Year'] = df['Date'].dt.year
        df['Month'] = df['Date'].dt.month
        df['Day'] = df['Date'].dt.day
        df['Hour'] = df['Date'].dt.hour
        df['DayOfWeek'] = df['Date'].dt.dayofweek
        df['DayOfYear'] = df['Date'].dt.dayofyear
        
        # Create region plastic type combinations
        df['Region_Plastic_Type'] = df['Region'] + '_' + df['Plastic_Type']
        
        # Validate coordinate ranges
        df = df[(df['Latitude'] >= -90) & (df['Latitude'] <= 90)]
        df = df[(df['Longitude'] >= -180) & (df['Longitude'] <= 180)]
        
        # Validate positive values
        df = df[df['Plastic_Weight_kg'] > 0]
        df = df[df['Depth_meters'] >= 0]
        
        print(f"Data cleaning complete. {len(df)} valid records remaining.")
        self.processed_data = df
        return df
    
    def aggregate_by_region_time(self, freq: str = 'D') -> pd.DataFrame:
        """
        Aggregate data by region and time period
        
        Args:
            freq: Frequency for time aggregation ('D'=daily, 'W'=weekly, 'M'=monthly)
            
        Returns:
            Aggregated DataFrame
        """
        if self.processed_data is None:
            self.clean_data()
            
        df = self.processed_data.copy()
        
        # Set date as index for resampling
        df.set_index('Date', inplace=True)
        
        # Aggregate by region and time period
        agg_data = df.groupby(['Region', pd.Grouper(freq=freq)]).agg({
            'Plastic_Weight_kg': ['sum', 'mean', 'std', 'count'],
            'Depth_meters': 'mean',
            'Latitude': 'mean',
            'Longitude': 'mean'
        }).reset_index()
        
        # Flatten column names
        agg_data.columns = ['_'.join(col).strip('_') for col in agg_data.columns.values]
        
        print(f"Aggregated data to {freq} frequency. {len(agg_data)} records.")
        return agg_data
    
    def aggregate_by_plastic_type_time(self, freq: str = 'D') -> pd.DataFrame:
        """
        Aggregate data by plastic type and time period
        
        Args:
            freq: Frequency for time aggregation
            
        Returns:
            Aggregated DataFrame by plastic type
        """
        if self.processed_data is None:
            self.clean_data()
            
        df = self.processed_data.copy()
        df.set_index('Date', inplace=True)
        
        agg_data = df.groupby(['Plastic_Type', pd.Grouper(freq=freq)]).agg({
            'Plastic_Weight_kg': ['sum', 'mean', 'std', 'count'],
            'Depth_meters': 'mean'
        }).reset_index()
        
        agg_data.columns = ['_'.join(col).strip('_') for col in agg_data.columns.values]
        
        print(f"Aggregated plastic type data to {freq} frequency. {len(agg_data)} records.")
        return agg_data
    
    def create_spatial_features(self) -> pd.DataFrame:
        """
        Create spatial features for geospatial analysis
        
        Returns:
            DataFrame with additional spatial features
        """
        if self.processed_data is None:
            self.clean_data()
            
        df = self.processed_data.copy()
        
        # Create distance from equator feature
        df['Distance_From_Equator'] = np.abs(df['Latitude'])
        
        # Create hemispheres
        df['Hemisphere'] = np.where(df['Latitude'] >= 0, 'Northern', 'Southern')
        
        # Create longitude zones
        df['Longitude_Zone'] = pd.cut(df['Longitude'], 
                                      bins=[-180, -90, 0, 90, 180],
                                      labels=['Western', 'Central_West', 'Central_East', 'Eastern'])
        
        # Create depth categories
        df['Depth_Category'] = pd.cut(df['Depth_meters'],
                                     bins=[0, 30, 60, 100],
                                     labels=['Shallow', 'Medium', 'Deep'])
        
        print("Spatial features created.")
        return df
    
    def get_summary_statistics(self) -> dict:
        """
        Generate summary statistics for the dataset
        
        Returns:
            Dictionary containing summary statistics
        """
        if self.processed_data is None:
            self.clean_data()
            
        df = self.processed_data
        
        stats = {
            'total_records': len(df),
            'date_range': (df['Date'].min(), df['Date'].max()),
            'regions': df['Region'].unique().tolist(),
            'plastic_types': df['Plastic_Type'].unique().tolist(),
            'total_plastic_weight_kg': df['Plastic_Weight_kg'].sum(),
            'avg_plastic_weight_kg': df['Plastic_Weight_kg'].mean(),
            'avg_depth_meters': df['Depth_meters'].mean(),
            'records_by_region': df['Region'].value_counts().to_dict(),
            'records_by_plastic_type': df['Plastic_Type'].value_counts().to_dict(),
            'plastic_by_region': df.groupby('Region')['Plastic_Weight_kg'].sum().to_dict()
        }
        
        return stats
    
    def save_processed_data(self, output_path: str):
        """
        Save processed data to CSV
        
        Args:
            output_path: Path to save the processed data
        """
        if self.processed_data is None:
            self.clean_data()
            
        self.processed_data.to_csv(output_path, index=False)
        print(f"Processed data saved to {output_path}")


def main():
    """Main function to test data processing"""
    # Initialize processor
    processor = OceanPlasticDataProcessor('data/raw/ocean_plastic_pollution_data.csv')
    
    # Load and clean data
    processor.load_data()
    processor.clean_data()
    
    # Create spatial features
    processor.create_spatial_features()
    
    # Generate summary statistics
    stats = processor.get_summary_statistics()
    print("\n=== Summary Statistics ===")
    for key, value in stats.items():
        print(f"{key}: {value}")
    
    # Save processed data
    os.makedirs('data/processed', exist_ok=True)
    processor.save_processed_data('data/processed/ocean_plastic_pollution_processed.csv')
    
    # Create aggregated datasets
    daily_region = processor.aggregate_by_region_time('D')
    daily_region.to_csv('data/processed/daily_by_region.csv', index=False)
    
    daily_plastic = processor.aggregate_by_plastic_type_time('D')
    daily_plastic.to_csv('data/processed/daily_by_plastic_type.csv', index=False)


if __name__ == "__main__":
    main()
