import sys
import json
from pathlib import Path

# Add backend directory to path so imports work
backend_dir = Path(__file__).parent.parent
sys.path.append(str(backend_dir))

from app.ml.preprocessing import clean_noaa_data

def main():
    raw_path = str(backend_dir / "data" / "raw" / "NOAA_raw.csv")
    processed_path = str(backend_dir / "data" / "processed" / "ocean_water_clean.csv")
    
    print("Starting data preprocessing...")
    report = clean_noaa_data(raw_path, processed_path)
    
    print("\n" + "="*40)
    print(" PREPROCESSING REPORT ")
    print("="*40)
    
    print(f"Original Rows:                  {report['original_rows']}")
    print(f"Rows after 'Ocean water' filter: {report['ocean_water_rows']}")
    print(f"Rows after 'pieces/m3' filter:   {report['pieces_per_m3_rows']}")
    print(f"Invalid/Missing Coordinates:    {report['invalid_coordinate_count']}")
    print(f"Missing Measurements:           {report['missing_measurement_count']}")
    print(f"Duplicate Rows Removed:         {report['duplicate_count']}")
    print(f"Final Cleaned Rows:             {report['final_rows']}")
    
    print("\n--- Value Ranges ---")
    print(f"Date Range:       {report['date_range']['min']} to {report['date_range']['max']}")
    print(f"Latitude Range:   {report['latitude_range']['min']:.4f} to {report['latitude_range']['max']:.4f}")
    print(f"Longitude Range:  {report['longitude_range']['min']:.4f} to {report['longitude_range']['max']:.4f}")
    
    print("\n--- Measurement Statistics ---")
    stats = report['measurement_statistics']
    print(f"Min:    {stats['min']:.4f}")
    print(f"Max:    {stats['max']:.4f}")
    print(f"Mean:   {stats['mean']:.4f}")
    print(f"Median: {stats['median']:.4f}")
    print(f"StdDev: {stats['std']:.4f}")
    
    print("="*40)
    print(f"\nCleaned dataset saved to: {processed_path}")

if __name__ == "__main__":
    main()
