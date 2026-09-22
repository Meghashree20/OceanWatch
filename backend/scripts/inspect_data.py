import pandas as pd
import sys

def inspect_dataset(file_path):
    print("Loading dataset...")
    df = pd.read_csv(file_path, low_memory=False)
    
    print("\n--- NOAA Data Inspection ---")
    print(f"Number of rows: {len(df)}")
    print(f"Number of columns: {len(df.columns)}")
    print("\nColumn names:")
    for col in df.columns:
        print(f" - {col}")
        
    print("\nData Types:")
    print(df.dtypes)
    
    print("\nMissing Values:")
    print(df.isnull().sum())
    
    # Try to find Marine Setting column
    setting_cols = [c for c in df.columns if 'setting' in c.lower() or 'marine' in c.lower()]
    if setting_cols:
        setting_col = setting_cols[0]
        print(f"\nUnique values in '{setting_col}':")
        print(df[setting_col].unique())
    else:
        print("\nCould not identify 'Marine Setting' column automatically.")
        
    # Try to find Unit column
    unit_cols = [c for c in df.columns if 'unit' in c.lower()]
    if unit_cols:
        unit_col = unit_cols[0]
        print(f"\nUnique values in '{unit_col}':")
        print(df[unit_col].unique())
    else:
        print("\nCould not identify 'Unit' column automatically.")
        
    # Try to find Date column
    date_cols = [c for c in df.columns if 'date' in c.lower()]
    if date_cols:
        date_col = date_cols[0]
        dates = pd.to_datetime(df[date_col], errors='coerce')
        print(f"\nDate range in '{date_col}':")
        print(f"Min: {dates.min()}, Max: {dates.max()}")
    else:
        print("\nCould not identify 'Date' column automatically.")
        
    print(f"\nExact Duplicate rows: {df.duplicated().sum()}")
    
if __name__ == '__main__':
    inspect_dataset(sys.argv[1])
