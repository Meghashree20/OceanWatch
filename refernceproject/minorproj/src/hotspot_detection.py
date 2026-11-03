"""
Hotspot Detection Module for OCEANWATCH
Uses DBSCAN clustering and spatial analysis to detect pollution hotspots
"""

import pandas as pd
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import silhouette_score
from scipy.stats import gaussian_kde
import joblib
import os
from typing import Tuple, Dict, List


class HotspotDetector:
    """Detect marine plastic pollution hotspots using spatial clustering"""
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize hotspot detector
        
        Args:
            data: Processed ocean plastic pollution data
        """
        self.data = data
        self.hotspots = None
        self.model = None
        self.scaler = StandardScaler()
        
    def prepare_spatial_data(self) -> np.ndarray:
        """
        Prepare spatial features for clustering
        
        Returns:
            Scaled feature matrix for clustering
        """
        # Select spatial features
        features = self.data[['Latitude', 'Longitude', 'Plastic_Weight_kg', 'Depth_meters']].values
        
        # Scale features
        scaled_features = self.scaler.fit_transform(features)
        
        return scaled_features
    
    def detect_hotspots_dbscan(self, eps: float = 0.3, min_samples: int = 5) -> pd.DataFrame:
        """
        Detect hotspots using DBSCAN clustering
        
        Args:
            eps: Maximum distance between samples for clustering
            min_samples: Minimum samples in a neighborhood
            
        Returns:
            DataFrame with cluster assignments and hotspot information
        """
        # Prepare features
        features = self.prepare_spatial_data()
        
        # Apply DBSCAN
        self.model = DBSCAN(eps=eps, min_samples=min_samples)
        clusters = self.model.fit_predict(features)
        
        # Add cluster labels to data
        result_df = self.data.copy()
        result_df['Cluster'] = clusters
        
        # Calculate cluster statistics
        try:
            hotspot_stats = self._calculate_cluster_statistics(result_df)
        except Exception as e:
            print(f"Error calculating cluster statistics: {e}")
            return result_df, pd.DataFrame()
        
        self.hotspots = result_df
        print(f"DBSCAN clustering complete. Found {len(hotspot_stats)} hotspots.")
        
        return result_df, hotspot_stats
    
    def _calculate_cluster_statistics(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate statistics for each cluster
        
        Args:
            df: DataFrame with cluster labels
            
        Returns:
            DataFrame with cluster statistics
        """
        # Filter out noise points (cluster = -1)
        clustered_data = df[df['Cluster'] != -1]
        
        if len(clustered_data) == 0:
            return pd.DataFrame()
        
        # Select only columns that exist in the dataframe
        available_columns = ['Latitude', 'Longitude', 'Plastic_Weight_kg', 'Depth_meters']
        aggregation_dict = {}
        
        for col in available_columns:
            if col in clustered_data.columns:
                if col in ['Latitude', 'Longitude']:
                    aggregation_dict[col] = ['mean', 'std', 'min', 'max']
                elif col == 'Plastic_Weight_kg':
                    aggregation_dict[col] = ['sum', 'mean', 'std', 'count']
                elif col == 'Depth_meters':
                    aggregation_dict[col] = ['mean', 'std']
        
        # Add Region if available
        if 'Region' in clustered_data.columns:
            aggregation_dict['Region'] = lambda x: x.mode()[0] if len(x.mode()) > 0 else 'Unknown'
        
        # Calculate statistics per cluster
        stats = clustered_data.groupby('Cluster').agg(aggregation_dict).reset_index()
        
        # Flatten column names
        stats.columns = ['_'.join(col).strip('_') for col in stats.columns.values]
        
        # Calculate hotspot intensity score (if weight columns exist)
        if 'Plastic_Weight_kg_sum' in stats.columns and 'Plastic_Weight_kg_count' in stats.columns:
            stats['Hotspot_Intensity_Score'] = (
                (stats['Plastic_Weight_kg_sum'] / stats['Plastic_Weight_kg_sum'].max()) * 0.6 +
                (stats['Plastic_Weight_kg_count'] / stats['Plastic_Weight_kg_count'].max()) * 0.4
            ) * 100
        else:
            stats['Hotspot_Intensity_Score'] = 50.0  # Default score
        
        # Calculate cluster area (approximate) if lat/lon columns exist
        if 'Latitude_min' in stats.columns and 'Latitude_max' in stats.columns:
            stats['Cluster_Area_km2'] = self._calculate_cluster_area(stats)
        else:
            stats['Cluster_Area_km2'] = 0.0
        
        # Sort by intensity score
        stats = stats.sort_values('Hotspot_Intensity_Score', ascending=False)
        
        return stats
    
    def _calculate_cluster_area(self, stats: pd.DataFrame) -> pd.Series:
        """
        Calculate approximate area of each cluster
        
        Args:
            stats: Cluster statistics DataFrame
            
        Returns:
            Series with cluster areas in km²
        """
        # Simple approximation using lat/lon bounds
        # 1 degree ≈ 111 km
        lat_range = stats['Latitude_max'] - stats['Latitude_min']
        lon_range = stats['Longitude_max'] - stats['Longitude_min']
        
        area = (lat_range * 111) * (lon_range * 111 * np.cos(np.radians(stats['Latitude_mean'])))
        
        return area
    
    def calculate_spatial_density(self, bandwidth: float = 0.5) -> np.ndarray:
        """
        Calculate spatial density using Kernel Density Estimation
        
        Args:
            bandwidth: Bandwidth for KDE
            
        Returns:
            Density values for each point
        """
        # Prepare coordinates
        coords = self.data[['Latitude', 'Longitude']].values
        
        # Calculate KDE
        kde = gaussian_kde(coords.T, bw_method=bandwidth)
        density = kde(coords.T)
        
        # Add density to data
        self.data['Spatial_Density'] = density
        
        return density
    
    def evaluate_clustering_quality(self) -> Dict[str, float]:
        """
        Evaluate clustering quality using various metrics
        
        Returns:
            Dictionary with clustering quality metrics
        """
        if self.hotspots is None:
            return {}
        
        # Filter out noise points
        clustered_data = self.hotspots[self.hotspots['Cluster'] != -1]
        
        if len(clustered_data) < 2:
            return {'error': 'Not enough clustered points for evaluation'}
        
        features = self.prepare_spatial_data()
        clustered_features = features[self.hotspots['Cluster'] != -1]
        cluster_labels = clustered_data['Cluster'].values
        
        metrics = {}
        
        # Silhouette score
        try:
            metrics['silhouette_score'] = silhouette_score(clustered_features, cluster_labels)
        except:
            metrics['silhouette_score'] = 0.0
        
        # Number of clusters
        metrics['n_clusters'] = len(clustered_data['Cluster'].unique())
        
        # Percentage of noise points
        metrics['noise_percentage'] = (len(self.hotspots[self.hotspots['Cluster'] == -1]) / len(self.hotspots)) * 100
        
        # Average cluster size
        metrics['avg_cluster_size'] = clustered_data.groupby('Cluster').size().mean()
        
        return metrics
    
    def get_top_hotspots(self, n: int = 10) -> pd.DataFrame:
        """
        Get top N hotspots by intensity score
        
        Args:
            n: Number of top hotspots to return
            
        Returns:
            DataFrame with top hotspots
        """
        if self.hotspots is None:
            return pd.DataFrame()
        
        try:
            hotspot_stats = self._calculate_cluster_statistics(self.hotspots)
            if len(hotspot_stats) == 0:
                return pd.DataFrame()
            return hotspot_stats.head(n)
        except Exception as e:
            print(f"Error getting top hotspots: {e}")
            return pd.DataFrame()
    
    def save_model(self, model_path: str):
        """
        Save the trained model and scaler
        
        Args:
            model_path: Path to save the model
        """
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'hotspots': self.hotspots
        }
        
        os.makedirs(os.path.dirname(model_path), exist_ok=True)
        joblib.dump(model_data, model_path)
        print(f"Model saved to {model_path}")
    
    def load_model(self, model_path: str):
        """
        Load a trained model
        
        Args:
            model_path: Path to the saved model
        """
        model_data = joblib.load(model_path)
        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.hotspots = model_data['hotspots']
        print(f"Model loaded from {model_path}")


def main():
    """Main function to test hotspot detection"""
    # Load processed data
    data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
    
    # Initialize detector
    detector = HotspotDetector(data)
    
    # Detect hotspots
    hotspots_df, hotspot_stats = detector.detect_hotspots_dbscan(eps=0.3, min_samples=15)
    
    # Calculate spatial density
    density = detector.calculate_spatial_density(bandwidth=0.3)
    
    # Evaluate clustering quality
    quality_metrics = detector.evaluate_clustering_quality()
    print("\n=== Clustering Quality Metrics ===")
    for key, value in quality_metrics.items():
        print(f"{key}: {value}")
    
    # Get top hotspots
    top_hotspots = detector.get_top_hotspots(10)
    print("\n=== Top 10 Hotspots ===")
    print(top_hotspots[['Cluster', 'Region', 'Hotspot_Intensity_Score', 
                        'Plastic_Weight_kg_sum', 'Cluster_Area_km2']])
    
    # Save model
    os.makedirs('data/models', exist_ok=True)
    detector.save_model('data/models/hotspot_detector.pkl')
    
    # Save results
    hotspots_df.to_csv('data/processed/hotspots_detected.csv', index=False)
    hotspot_stats.to_csv('data/processed/hotspot_statistics.csv', index=False)


if __name__ == "__main__":
    main()
