import csv
from collections import Counter
import sys

def inspect_csv(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            
            if not header:
                print("Empty CSV")
                return
            
            print("--- NOAA CSV Inspection ---")
            print(f"Number of columns: {len(header)}")
            print("\nColumns:")
            for i, col in enumerate(header):
                print(f"{i}: {col}")
            
            # Find indices for important columns
            setting_idx = next((i for i, c in enumerate(header) if 'setting' in c.lower() or 'marine' in c.lower()), -1)
            unit_idx = next((i for i, c in enumerate(header) if 'unit' in c.lower()), -1)
            
            setting_counts = Counter()
            unit_counts = Counter()
            
            row_count = 0
            for row in reader:
                row_count += 1
                if setting_idx != -1 and setting_idx < len(row):
                    setting_counts[row[setting_idx]] += 1
                if unit_idx != -1 and unit_idx < len(row):
                    unit_counts[row[unit_idx]] += 1
                    
            print(f"\nTotal rows (excluding header): {row_count}")
            
            if setting_idx != -1:
                print(f"\nUnique values in '{header[setting_idx]}':")
                for k, v in setting_counts.most_common():
                    print(f" - '{k}': {v}")
                    
            if unit_idx != -1:
                print(f"\nUnique values in '{header[unit_idx]}':")
                for k, v in unit_counts.most_common():
                    print(f" - '{k}': {v}")
                    
    except Exception as e:
        print(f"Error reading CSV: {e}")

if __name__ == "__main__":
    inspect_csv(sys.argv[1])
