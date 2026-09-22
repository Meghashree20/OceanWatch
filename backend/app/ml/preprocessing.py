import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, Any

def clean_noaa_data(input_path: str, output_path: str) -> Dict[str, Any]:
    """
    Cleans the NOAA Marine Microplastics dataset based on Phase 2 requirements.
    Returns a report dictionary containing statistics.
    """
    df = pd.read_csv(input_path, low_memory=False)
    report = {}
    report["original_rows"] = len(df)
    
    # 3. Select only Marine Setting = "Ocean water"
    ocean_water_mask = df["Marine Setting"].astype(str).str.strip().str.lower() == "ocean water"
    df_ocean = df[ocean_water_mask]
    report["ocean_water_rows"] = len(df_ocean)
    
    # 4. Select only Unit = "pieces/m3"
    unit_mask = df_ocean["Unit"].astype(str).str.strip().str.lower() == "pieces/m3"
    df_filtered = df_ocean[unit_mask].copy()
    report["pieces_per_m3_rows"] = len(df_filtered)
    
    # 5. Convert Sample Date to proper datetime
    df_filtered["Sample Date"] = pd.to_datetime(df_filtered["Sample Date"], errors="coerce")
    
    # 6. Convert to numeric
    numeric_cols = ["Latitude (degree)", "Longitude (degree)", "Microplastics Measurement"]
    for col in numeric_cols:
        df_filtered[col] = pd.to_numeric(df_filtered[col], errors="coerce")
        
    # 7 & 8. Validate coordinates and remove missings
    report["missing_measurement_count"] = df_filtered["Microplastics Measurement"].isnull().sum()
    
    valid_lat = df_filtered["Latitude (degree)"].between(-90, 90)
    valid_lon = df_filtered["Longitude (degree)"].between(-180, 180)
    
    invalid_coord_mask = ~valid_lat | ~valid_lon | df_filtered["Latitude (degree)"].isnull() | df_filtered["Longitude (degree)"].isnull()
    report["invalid_coordinate_count"] = invalid_coord_mask.sum()
    
    # Apply filtering for non-missing and valid coordinates
    df_clean = df_filtered[~invalid_coord_mask & df_filtered["Microplastics Measurement"].notnull()].copy()
    
    # 9. Remove exact duplicates
    duplicate_mask = df_clean.duplicated()
    report["duplicate_count"] = duplicate_mask.sum()
    df_clean = df_clean[~duplicate_mask].copy()
    
    # Calculate final stats for report
    report["final_rows"] = len(df_clean)
    report["date_range"] = {
        "min": df_clean["Sample Date"].min().strftime("%Y-%m-%d") if pd.notnull(df_clean["Sample Date"].min()) else None,
        "max": df_clean["Sample Date"].max().strftime("%Y-%m-%d") if pd.notnull(df_clean["Sample Date"].max()) else None
    }
    report["latitude_range"] = {
        "min": df_clean["Latitude (degree)"].min(),
        "max": df_clean["Latitude (degree)"].max()
    }
    report["longitude_range"] = {
        "min": df_clean["Longitude (degree)"].min(),
        "max": df_clean["Longitude (degree)"].max()
    }
    report["measurement_statistics"] = {
        "min": df_clean["Microplastics Measurement"].min(),
        "max": df_clean["Microplastics Measurement"].max(),
        "mean": df_clean["Microplastics Measurement"].mean(),
        "median": df_clean["Microplastics Measurement"].median(),
        "std": df_clean["Microplastics Measurement"].std()
    }
    
    # 11. Preserve metadata (keep columns). Just saving everything.
    
    # 12. Save cleaned dataset
    output_dir = Path(output_path).parent
    output_dir.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(output_path, index=False)
    
    return report
