"""
Time-Series Forecasting Module for OCEANWATCH
Uses Prophet to forecast future pollution levels
"""

import pandas as pd
import numpy as np
from prophet import Prophet
from prophet.diagnostics import cross_validation, performance_metrics
from sklearn.metrics import mean_absolute_error, mean_squared_error
import joblib
import os
from typing import Dict, List, Tuple
import warnings
warnings.filterwarnings('ignore')


class PollutionForecaster:
    """Forecast marine plastic pollution using time-series analysis"""
    
    def __init__(self, data: pd.DataFrame):
        """
        Initialize pollution forecaster
        
        Args:
            data: Processed ocean plastic pollution data
        """
        self.data = data
        self.models = {}  # Dictionary to store models for different regions/plastic types
        self.forecasts = {}  # Dictionary to store forecasts
        self.metrics = {}  # Dictionary to store model performance metrics
        
    def prepare_time_series_data(self, groupby_column: str = 'Region') -> Dict[str, pd.DataFrame]:
        """
        Prepare time series data for forecasting
        
        Args:
            groupby_column: Column to group by (Region, Plastic_Type, or combination)
            
        Returns:
            Dictionary of time series DataFrames by group
        """
        # Ensure date is datetime
        self.data['Date'] = pd.to_datetime(self.data['Date'])
        
        # Aggregate daily data by group
        daily_data = self.data.groupby([groupby_column, pd.Grouper(key='Date', freq='D')]).agg({
            'Plastic_Weight_kg': 'sum'
        }).reset_index()
        
        # Split into dictionary by group
        time_series_dict = {}
        for group_name, group_data in daily_data.groupby(groupby_column):
            # Prepare for Prophet: ds and y columns
            prophet_data = group_data[['Date', 'Plastic_Weight_kg']].copy()
            prophet_data.columns = ['ds', 'y']
            
            # Remove any zero or negative values
            prophet_data = prophet_data[prophet_data['y'] > 0]
            
            if len(prophet_data) > 10:  # Need minimum data points
                time_series_dict[group_name] = prophet_data
        
        print(f"Prepared time series data for {len(time_series_dict)} groups.")
        return time_series_dict
    
    def train_forecast_model(self, time_series_data: pd.DataFrame, 
                            group_name: str = 'default') -> Prophet:
        """
        Train a Prophet forecasting model for a single time series
        
        Args:
            time_series_data: Time series data with 'ds' and 'y' columns
            group_name: Name of the group being forecasted
            
        Returns:
            Trained Prophet model
        """
        # Initialize Prophet model with optimized parameters
        model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=True,
            daily_seasonality=False,  # Daily seasonality not needed for daily data
            changepoint_prior_scale=0.05,  # Conservative trend changes
            seasonality_prior_scale=10.0,  # Allow strong seasonality
            holidays_prior_scale=10.0,
            interval_width=0.8,  # 80% confidence intervals
            mcmc_samples=0  # Use MAP estimation for speed
        )
        
        # Fit the model
        model.fit(time_series_data)
        
        self.models[group_name] = model
        print(f"Model trained for {group_name}")
        
        return model
    
    def generate_forecast(self, model: Prophet, periods: int = 30, 
                         group_name: str = 'default') -> pd.DataFrame:
        """
        Generate future predictions using trained model
        
        Args:
            model: Trained Prophet model
            periods: Number of days to forecast
            group_name: Name of the group
            
        Returns:
            DataFrame with forecast
        """
        # Create future dataframe
        future = model.make_future_dataframe(periods=periods)
        
        # Generate forecast
        forecast = model.predict(future)
        
        self.forecasts[group_name] = forecast
        print(f"Forecast generated for {group_name} ({periods} days)")
        
        return forecast
    
    def evaluate_model(self, model: Prophet, time_series_data: pd.DataFrame,
                      group_name: str = 'default') -> Dict[str, float]:
        """
        Evaluate model performance using cross-validation
        
        Args:
            model: Trained Prophet model
            time_series_data: Original time series data
            group_name: Name of the group
            
        Returns:
            Dictionary with performance metrics
        """
        # Perform cross-validation
        try:
            cv_results = cross_validation(
                model, 
                initial='180 days',  # Training period
                period='30 days',   # Spacing between cutoffs
                horizon='30 days',  # Forecast horizon
                parallel='processes'
            )
            
            # Calculate performance metrics
            metrics = performance_metrics(cv_results)
            
            # Extract key metrics
            performance = {
                'mae': metrics['mae'].mean(),
                'rmse': metrics['rmse'].mean(),
                'mape': metrics['mape'].mean(),
                'coverage': metrics['coverage'].mean()
            }
            
        except Exception as e:
            print(f"Cross-validation failed for {group_name}: {e}")
            # Fallback to simple train-test split
            train_size = int(len(time_series_data) * 0.8)
            train_data = time_series_data[:train_size]
            test_data = time_series_data[train_size:]
            
            # Train on training data
            temp_model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=True,
                daily_seasonality=False
            )
            temp_model.fit(train_data)
            
            # Forecast for test period
            future = temp_model.make_future_dataframe(periods=len(test_data))
            forecast = temp_model.predict(future)
            
            # Extract predictions for test period
            predictions = forecast.tail(len(test_data))['yhat'].values
            actual = test_data['y'].values
            
            # Calculate metrics
            performance = {
                'mae': mean_absolute_error(actual, predictions),
                'rmse': np.sqrt(mean_squared_error(actual, predictions)),
                'mape': np.mean(np.abs((actual - predictions) / actual)) * 100,
                'coverage': 0.0  # Not available in simple split
            }
        
        self.metrics[group_name] = performance
        print(f"Model evaluation complete for {group_name}")
        
        return performance
    
    def train_all_models(self, groupby_column: str = 'Region', 
                        forecast_periods: int = 30) -> Dict[str, pd.DataFrame]:
        """
        Train models and generate forecasts for all groups
        
        Args:
            groupby_column: Column to group by
            forecast_periods: Number of days to forecast
            
        Returns:
            Dictionary of forecasts for all groups
        """
        # Prepare time series data
        time_series_dict = self.prepare_time_series_data(groupby_column)
        
        # Train model for each group
        for group_name, ts_data in time_series_dict.items():
            try:
                # Train model
                model = self.train_forecast_model(ts_data, group_name)
                
                # Generate forecast
                forecast = self.generate_forecast(model, forecast_periods, group_name)
                
                # Evaluate model
                metrics = self.evaluate_model(model, ts_data, group_name)
                
            except Exception as e:
                print(f"Error processing {group_name}: {e}")
                continue
        
        print(f"\nTraining complete. Models trained for {len(self.models)} groups.")
        return self.forecasts
    
    def get_forecast_summary(self) -> pd.DataFrame:
        """
        Get summary of all forecasts and model performance
        
        Returns:
            DataFrame with forecast summary
        """
        summary_data = []
        
        for group_name, forecast in self.forecasts.items():
            # Get the forecast portion only (future dates)
            future_forecast = forecast[forecast['ds'] > forecast['ds'].max() - pd.Timedelta(days=30)]
            
            # Calculate summary statistics
            summary = {
                'Group': group_name,
                'Forecast_Period_Start': future_forecast['ds'].min(),
                'Forecast_Period_End': future_forecast['ds'].max(),
                'Predicted_Total_Pollution_kg': future_forecast['yhat'].sum(),
                'Predicted_Avg_Daily_Pollution_kg': future_forecast['yhat'].mean(),
                'Predicted_Max_Pollution_kg': future_forecast['yhat'].max(),
                'Trend_Direction': 'Increasing' if future_forecast['yhat'].iloc[-1] > future_forecast['yhat'].iloc[0] else 'Decreasing',
                'MAE': self.metrics.get(group_name, {}).get('mae', 0),
                'RMSE': self.metrics.get(group_name, {}).get('rmse', 0),
                'MAPE': self.metrics.get(group_name, {}).get('mape', 0)
            }
            
            summary_data.append(summary)
        
        return pd.DataFrame(summary_data)
    
    def save_models(self, model_dir: str):
        """
        Save all trained models
        
        Args:
            model_dir: Directory to save models
        """
        os.makedirs(model_dir, exist_ok=True)
        
        for group_name, model in self.models.items():
            # Sanitize group name for filename
            safe_name = group_name.replace('/', '_').replace('\\', '_').replace(' ', '_')
            model_path = os.path.join(model_dir, f'forecast_model_{safe_name}.pkl')
            joblib.dump(model, model_path)
        
        # Save forecasts and metrics
        joblib.dump(self.forecasts, os.path.join(model_dir, 'forecasts.pkl'))
        joblib.dump(self.metrics, os.path.join(model_dir, 'metrics.pkl'))
        
        print(f"All models saved to {model_dir}")
    
    def load_models(self, model_dir: str):
        """
        Load trained models
        
        Args:
            model_dir: Directory containing saved models
        """
        # Load forecasts and metrics
        self.forecasts = joblib.load(os.path.join(model_dir, 'forecasts.pkl'))
        self.metrics = joblib.load(os.path.join(model_dir, 'metrics.pkl'))
        
        # Load individual models
        for file in os.listdir(model_dir):
            if file.startswith('forecast_model_') and file.endswith('.pkl'):
                group_name = file.replace('forecast_model_', '').replace('.pkl', '_')
                group_name = group_name.replace('_', ' ')  # Reverse sanitization
                model_path = os.path.join(model_dir, file)
                self.models[group_name] = joblib.load(model_path)
        
        print(f"Models loaded from {model_dir}")


def main():
    """Main function to test forecasting"""
    # Load processed data
    data = pd.read_csv('data/processed/ocean_plastic_pollution_processed.csv')
    
    # Initialize forecaster
    forecaster = PollutionForecaster(data)
    
    # Train models for each region
    forecasts = forecaster.train_all_models(groupby_column='Region', forecast_periods=30)
    
    # Get forecast summary
    summary = forecaster.get_forecast_summary()
    print("\n=== Forecast Summary ===")
    print(summary)
    
    # Save models
    os.makedirs('data/models', exist_ok=True)
    forecaster.save_models('data/models')
    
    # Save summary
    summary.to_csv('data/processed/forecast_summary.csv', index=False)


if __name__ == "__main__":
    main()
