import pandas as pd
import numpy as np

# Load the dataset
df = pd.read_csv(r'C:\Users\Anushka\.cache\kagglehub\datasets\aniruddhawankhede\oceanplasticpollution\versions\1\ocean_plastic_pollution_data.csv')

print(f"Total rows: {len(df)}")
print(f"Columns: {df.columns.tolist()}")
print(f"\nDate range: {df['Date'].min()} to {df['Date'].max()}")
print(f"\nRegions: {df['Region'].unique()}")
print(f"\nPlastic types: {df['Plastic_Type'].unique()}")

print(f"\nBasic statistics:")
print(df.describe())

print(f"\nMissing values:")
print(df.isnull().sum())

print(f"\nData types:")
print(df.dtypes)
