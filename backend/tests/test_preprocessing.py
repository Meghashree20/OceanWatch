import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from app.ml.preprocessing import clean_noaa_data

@pytest.fixture
def mock_csv(tmp_path):
    data = {
        "Marine Setting": ["Ocean water", "Beach", "Ocean water", "Ocean water", "Ocean water", "Ocean water", "Ocean water", "Ocean water"],
        "Unit": ["pieces/m3", "pieces/m3", "pieces/L", "pieces/m3", "pieces/m3", "pieces/m3", "pieces/m3", "pieces/m3"],
        "Sample Date": ["2020-01-01", "2020-01-02", "2020-01-03", "invalid-date", "2020-01-05", "2020-01-06", "2020-01-06", "2020-01-07"],
        "Latitude (degree)": [10.0, 10.0, 10.0, 95.0, np.nan, 10.0, 10.0, 10.0], # 95.0 is invalid, one is NaN
        "Longitude (degree)": [20.0, 20.0, 20.0, 20.0, 20.0, 200.0, 200.0, 20.0], # 200.0 is invalid
        "Microplastics Measurement": [1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 6.0, np.nan] # one NaN, one duplicate (idx 5 and 6)
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "mock_raw.csv"
    df.to_csv(csv_path, index=False)
    return str(csv_path)

def test_clean_noaa_data(mock_csv, tmp_path):
    output_path = str(tmp_path / "clean.csv")
    report = clean_noaa_data(mock_csv, output_path)
    
    assert report["original_rows"] == 8
    
    # 1 Beach row removed, leaving 7
    assert report["ocean_water_rows"] == 7
    
    # 1 pieces/L removed, leaving 6
    assert report["pieces_per_m3_rows"] == 6
    
    # Missing measurement = 1
    assert report["missing_measurement_count"] == 1
    
    # Invalid/missing coords = 3 (idx 3 is lat 95, idx 4 is lat NaN, idx 5 and 6 are lon 200)
    # wait: idx 3, 4, 5, 6 are invalid. total 4.
    assert report["invalid_coordinate_count"] == 4
    
    # Exact duplicate = 1 (idx 5 and 6 are duplicates, but they both have invalid coords so they might get dropped first)
    # Actually duplicates are checked AFTER dropping invalid/missing.
    # Rows passing filter: idx 0.
    # Wait, let's trace:
    # 0: valid
    # 1: Beach (dropped)
    # 2: pieces/L (dropped)
    # 3: lat 95 (dropped)
    # 4: lat NaN (dropped)
    # 5: lon 200 (dropped)
    # 6: lon 200 (duplicate of 5, dropped)
    # 7: NaN measurement (dropped)
    # Only row 0 should remain.
    assert report["final_rows"] == 1
    
    df_clean = pd.read_csv(output_path)
    assert len(df_clean) == 1
    assert df_clean.iloc[0]["Microplastics Measurement"] == 1.5
