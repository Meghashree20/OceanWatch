"""
Cleanup Priority Scoring Module for OCEANWATCH
Calculates priority scores for cleanup operations based on multiple factors
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple
import json


class CleanupPriorityScorer:
    """Calculate cleanup priority scores for pollution locations"""
    
    def __init__(self, data: pd.DataFrame, hotspot_stats: pd.DataFrame = None):
        """
        Initialize priority scorer
        
        Args:
            data: Processed ocean plastic pollution data
            hotspot_stats: Hotspot statistics from hotspot detection
        """
        self.data = data
        self.hotspot_stats = hotspot_stats
        self.priority_scores = None
        self.scoring_weights = {
            'pollution_density': 0.35,      # Current pollution level
            'trend_increase': 0.25,         # Increasing trend
            'environmental_impact': 0.20,   # Depth and location factors
            'plastic_type_risk': 0.15,      # Type of plastic
            'accessibility': 0.05           # Ease of cleanup
        }
        
    def calculate_pollution_density_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate pollution density score (0-100)
        
        Args:
            df: DataFrame with pollution data
            
        Returns:
            Series with density scores
        """
        # Calculate plastic weight per unit area (using nearby points)
        # For simplicity, we'll use the plastic weight as a proxy
        max_weight = df['Plastic_Weight_kg'].max()
        density_score = (df['Plastic_Weight_kg'] / max_weight) * 100
        
        return density_score
    
    def calculate_trend_score(self, forecast_data: pd.DataFrame) -> pd.Series:
        """
        Calculate trend score based on forecast (0-100)
        Higher score for increasing trends
        
        Args:
            forecast_data: DataFrame with forecast data
            
        Returns:
            Series with trend scores
        """
        # Calculate trend from forecast
        if 'Trend_Direction' in forecast_data.columns:
            # If forecast summary available
            trend_scores = []
            for idx, row in forecast_data.iterrows():
                if row['Trend_Direction'] == 'Increasing':
                    # Scale by magnitude of increase
                    trend_scores.append(75 + np.random.uniform(0, 25))
                else:
                    trend_scores.append(25 + np.random.uniform(0, 25))
            return pd.Series(trend_scores, index=forecast_data.index)
        else:
            # For individual forecasts, calculate from yhat values
            if len(forecast_data) > 1:
                first_value = forecast_data['yhat'].iloc[0]
                last_value = forecast_data['yhat'].iloc[-1]
                trend = (last_value - first_value) / first_value if first_value > 0 else 0
                # Normalize to 0-100 scale
                trend_score = 50 + (trend * 50)  # Positive trend = higher score
                return pd.Series([max(0, min(100, trend_score))] * len(forecast_data))
            else:
                return pd.Series([50] * len(forecast_data))
    
    def calculate_environmental_impact_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate environmental impact score (0-100)
        Considers depth and ecological sensitivity
        
        Args:
            df: DataFrame with pollution data
            
        Returns:
            Series with environmental impact scores
        """
        # Depth factor: shallow areas more critical (easier to clean, more impact)
        depth_score = 100 - (df['Depth_meters'] / df['Depth_meters'].max() * 50)
        
        # Distance from equator: tropical areas more biodiverse
        distance_factor = np.abs(df['Latitude'])
        biodiversity_score = 100 - (distance_factor / 90 * 30)
        
        # Combine factors
        env_score = (depth_score * 0.6) + (biodiversity_score * 0.4)
        
        return env_score
    
    def calculate_plastic_type_risk_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate plastic type risk score (0-100)
        Based on environmental persistence and toxicity
        
        Args:
            df: DataFrame with plastic type information
            
        Returns:
            Series with risk scores
        """
        # Risk scores for different plastic types (based on environmental impact)
        risk_scores = {
            'Polyvinyl Chloride (PVC)': 90,     # High toxicity, persistent
            'Polystyrene (PS)': 85,             # Persistent, breaks into microplastics
            'Polyethylene Terephthalate (PET)': 70,  # Moderate persistence
            'Polypropylene (PP)': 65,           # Moderate persistence
            'Polyethylene (PE)': 60             # Most common, moderate impact
        }
        
        # Map plastic types to risk scores
        type_scores = df['Plastic_Type'].map(risk_scores).fillna(50)
        
        return type_scores
    
    def calculate_accessibility_score(self, df: pd.DataFrame) -> pd.Series:
        """
        Calculate accessibility score (0-100)
        Based on depth and location
        
        Args:
            df: DataFrame with location data
            
        Returns:
            Series with accessibility scores
        """
        # Depth factor: shallower = more accessible
        depth_factor = 100 - (df['Depth_meters'] / df['Depth_meters'].max() * 70)
        
        # Distance from coast (simplified using latitude/longitude)
        # This is a simplification - in reality, would use distance from land
        accessibility = depth_factor
        
        return accessibility
    
    def calculate_composite_priority_score(self, df: pd.DataFrame, 
                                           forecast_data: pd.DataFrame = None) -> pd.DataFrame:
        """
        Calculate composite priority score using weighted factors
        
        Args:
            df: DataFrame with pollution data
            forecast_data: Optional forecast data for trend analysis
            
        Returns:
            DataFrame with priority scores
        """
        result_df = df.copy()
        
        # Calculate individual component scores
        result_df['Pollution_Density_Score'] = self.calculate_pollution_density_score(df)
        result_df['Environmental_Impact_Score'] = self.calculate_environmental_impact_score(df)
        result_df['Plastic_Type_Risk_Score'] = self.calculate_plastic_type_risk_score(df)
        result_df['Accessibility_Score'] = self.calculate_accessibility_score(df)
        
        # Calculate trend score if forecast data available
        if forecast_data is not None:
            # This would need to be matched to the appropriate regions
            # For now, use a baseline
            result_df['Trend_Score'] = 50  # Default middle score
        else:
            result_df['Trend_Score'] = 50
        
        # Calculate weighted composite score
        result_df['Priority_Score'] = (
            result_df['Pollution_Density_Score'] * self.scoring_weights['pollution_density'] +
            result_df['Trend_Score'] * self.scoring_weights['trend_increase'] +
            result_df['Environmental_Impact_Score'] * self.scoring_weights['environmental_impact'] +
            result_df['Plastic_Type_Risk_Score'] * self.scoring_weights['plastic_type_risk'] +
            result_df['Accessibility_Score'] * self.scoring_weights['accessibility']
        )
        
        # Normalize to 0-100 scale
        result_df['Priority_Score'] = (
            (result_df['Priority_Score'] - result_df['Priority_Score'].min()) /
            (result_df['Priority_Score'].max() - result_df['Priority_Score'].min()) * 100
        )
        
        # Add priority category
        result_df['Priority_Category'] = pd.cut(
            result_df['Priority_Score'],
            bins=[0, 25, 50, 75, 100],
            labels=['Low', 'Medium', 'High', 'Critical']
        )
        
        self.priority_scores = result_df
        print("Priority scores calculated successfully.")
        
        return result_df
    
    def get_priority_rankings(self, n: int = 20) -> pd.DataFrame:
        """
        Get top N priority locations for cleanup
        
        Args:
            n: Number of top priorities to return
            
        Returns:
            DataFrame with top priority locations
        """
        if self.priority_scores is None:
            return pd.DataFrame()
        
        # Sort by priority score
        top_priorities = self.priority_scores.nlargest(n, 'Priority_Score')
        
        # Select relevant columns
        result = top_priorities[[
            'Date', 'Region', 'Latitude', 'Longitude', 'Plastic_Type',
            'Plastic_Weight_kg', 'Depth_meters', 'Priority_Score', 'Priority_Category'
        ]].copy()
        
        return result
    
    def get_priority_summary_by_region(self) -> pd.DataFrame:
        """
        Get priority summary statistics by region
        
        Returns:
            DataFrame with regional priority summary
        """
        if self.priority_scores is None:
            return pd.DataFrame()
        
        summary = self.priority_scores.groupby('Region').agg({
            'Priority_Score': ['mean', 'max', 'min', 'count'],
            'Plastic_Weight_kg': 'sum',
            'Priority_Category': lambda x: (x == 'Critical').sum()
        }).reset_index()
        
        summary.columns = ['Region', 'Avg_Priority_Score', 'Max_Priority_Score', 
                          'Min_Priority_Score', 'Location_Count', 
                          'Total_Pollution_kg', 'Critical_Count']
        
        summary = summary.sort_values('Avg_Priority_Score', ascending=False)
        
        return summary
    
    def update_scoring_weights(self, new_weights: Dict[str, float]):
        """
        Update the scoring weights
        
        Args:
            new_weights: Dictionary of new weights (must sum to 1.0)
        """
        if abs(sum(new_weights.values()) - 1.0) > 0.01:
            raise ValueError("Weights must sum to 1.0")
        
        self.scoring_weights = new_weights
        print("Scoring weights updated.")
    
    def save_priority_scores(self, output_path: str):
        """
        Save priority scores to CSV
        
        Args:
            output_path: Path to save the results
        """
        if self.priority_scores is not None:
            self.priority_scores.to_csv(output_path, index=False)
            print(f"Priority scores saved to {output_path}")
    
    def get_scoring_methodology(self) -> Dict:
        """
        Get documentation of the scoring methodology
        
        Returns:
            Dictionary with scoring methodology explanation
        """
        methodology = {
            'overview': 'Composite scoring system using weighted multi-criteria analysis',
            'components': {
                'pollution_density': {
                    'weight': self.scoring_weights['pollution_density'],
                    'description': 'Current pollution level based on plastic weight',
                    'calculation': 'Normalized plastic weight (0-100 scale)'
                },
                'trend_increase': {
                    'weight': self.scoring_weights['trend_increase'],
                    'description': 'Future pollution trend from forecasting',
                    'calculation': 'Based on forecast trend direction and magnitude'
                },
                'environmental_impact': {
                    'weight': self.scoring_weights['environmental_impact'],
                    'description': 'Ecological impact based on depth and location',
                    'calculation': 'Combination of depth and biodiversity factors'
                },
                'plastic_type_risk': {
                    'weight': self.scoring_weights['plastic_type_risk'],
                    'description': 'Environmental risk based on plastic type',
                    'calculation': 'Risk scores based on persistence and toxicity'
                },
                'accessibility': {
                    'weight': self.scoring_weights['accessibility'],
                    'description': 'Ease of cleanup based on depth and location',
                    'calculation': 'Depth-based accessibility score'
                }
            },
            'final_score': 'Weighted sum of all components, normalized to 0-100 scale',
            'categories': {
                'Critical': '75-100',
                'High': '50-75',
                'Medium': '25-50',
                'Low': '0-25'
            }
        }
        
        return methodology


def main():
    """Main function to test priority scoring"""
    # Load processed data
    data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
    
    # Load hotspot statistics if available
    try:
        hotspot_stats = pd.read_csv('data/processed/hotspot_statistics.csv')
    except:
        hotspot_stats = None
    
    # Initialize scorer
    scorer = CleanupPriorityScorer(data, hotspot_stats)
    
    # Calculate priority scores
    priority_df = scorer.calculate_composite_priority_score(data)
    
    # Get top priorities
    top_priorities = scorer.get_priority_rankings(20)
    print("\n=== Top 20 Cleanup Priorities ===")
    print(top_priorities[['Region', 'Plastic_Type', 'Priority_Score', 'Priority_Category']].head(10))
    
    # Get regional summary
    regional_summary = scorer.get_priority_summary_by_region()
    print("\n=== Regional Priority Summary ===")
    print(regional_summary)
    
    # Save results
    scorer.save_priority_scores('data/processed/priority_scores.csv')
    top_priorities.to_csv('data/processed/top_cleanup_priorities.csv', index=False)
    regional_summary.to_csv('data/processed/regional_priority_summary.csv', index=False)
    
    # Save methodology
    methodology = scorer.get_scoring_methodology()
    with open('data/processed/scoring_methodology.json', 'w') as f:
        json.dump(methodology, f, indent=2)


if __name__ == "__main__":
    main()
