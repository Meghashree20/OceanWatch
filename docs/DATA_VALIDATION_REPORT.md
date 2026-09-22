# OceanWatch Real NOAA Data Validation Report

Validation date: 2026-09-08

## Status

**PASS**

The raw and processed NOAA files were inspected directly with pandas. No expected values were hard-coded. The existing backend test suite was run after validation.

## 1. Raw Data Validation

File: `backend/data/raw/NOAA_raw.csv`

- Total rows: **8,340**
- Total columns: **35**
- Duplicate rows: **0**
- Valid sample dates: **8,340**
- Invalid sample dates: **0**
- Date range: **2010-01-09 06:00:00** through **2024-10-23 05:00:00**

### Column names and data types

| Column | Data type |
| --- | --- |
| Unique ID | `str` |
| Sample Date | `str` |
| Latitude (degree) | `float64` |
| Longitude (degree) | `float64` |
| Ocean | `str` |
| Region | `str` |
| Subregion | `str` |
| Country | `str` |
| State | `str` |
| Beach Location | `str` |
| Marine Setting | `str` |
| Ocean Bottom Depth (m) | `float64` |
| Water Sample Depth (m) | `float64` |
| Sediment Sample Depth (m) | `float64` |
| Sampling Method | `str` |
| Mesh Size (mm) | `float64` |
| Transect Number | `float64` |
| Sampling Point on Beach | `float64` |
| Volunteers Number | `float64` |
| Collecting Time (min) | `float64` |
| Standardized Nurdle  Amount | `float64` |
| Microplastics Measurement | `float64` |
| Unit | `str` |
| Concentration Class Range | `str` |
| Concentration Class | `str` |
| Short Reference | `str` |
| Long Reference | `str` |
| DOI | `str` |
| Organization | `str` |
| Keywords | `str` |
| NCEI Accession Number | `int64` |
| NCEI Accession Link | `str` |
| ObjectId | `int64` |
| x | `float64` |
| y | `float64` |

### Missing values per column

| Column | Missing values |
| --- | ---: |
| Unique ID | 0 |
| Sample Date | 0 |
| Latitude (degree) | 0 |
| Longitude (degree) | 0 |
| Ocean | 0 |
| Region | 4,150 |
| Subregion | 6,681 |
| Country | 7,271 |
| State | 7,724 |
| Beach Location | 7,250 |
| Marine Setting | 0 |
| Ocean Bottom Depth (m) | 8,008 |
| Water Sample Depth (m) | 1,526 |
| Sediment Sample Depth (m) | 7,660 |
| Sampling Method | 0 |
| Mesh Size (mm) | 47 |
| Transect Number | 8,042 |
| Sampling Point on Beach | 7,780 |
| Volunteers Number | 8,340 |
| Collecting Time (min) | 8,340 |
| Standardized Nurdle  Amount | 8,340 |
| Microplastics Measurement | 0 |
| Unit | 0 |
| Concentration Class Range | 0 |
| Concentration Class | 0 |
| Short Reference | 0 |
| Long Reference | 0 |
| DOI | 0 |
| Organization | 0 |
| Keywords | 1,130 |
| NCEI Accession Number | 0 |
| NCEI Accession Link | 0 |
| ObjectId | 0 |
| x | 7 |
| y | 7 |

### Raw categorical values

`Marine Setting` values:

- Ocean water
- Ocean sediment
- Beach

`Unit` values:

- pieces/m3
- pieces kg-1 d.w.

`Study Type`: **the column is absent from the raw NOAA file**, so no Study Type values are available to report.

## 2. Processed Data Validation

File: `backend/data/processed/ocean_water_clean.csv`

- Final cleaned rows: **6,867**
- Columns: **35**
- Marine Setting `Ocean water`: **6,867**
- Unit `pieces/m3`: **6,867**
- Valid numeric measurements: **6,867**
- Invalid/non-numeric measurements: **0**
- Valid dates: **6,867**
- Invalid dates: **0**
- Valid coordinates: **6,867**
- Invalid coordinate rows: **0**
- Missing required values: **0**
- Duplicate rows: **0**

### Preprocessing comparison

| Check | Count |
| --- | ---: |
| Raw records | 8,340 |
| Raw Ocean water records | 6,867 |
| Raw Ocean water + pieces/m3 records | 6,867 |
| Raw invalid coordinate rows | 0 |
| Raw missing measurements | 0 |
| Raw invalid dates | 0 |
| Raw duplicate rows | 0 |
| Final cleaned records | 6,867 |

Processed date range: **2010-01-09 06:00:00** through **2024-10-23 05:00:00**.

## 3. Statistical Summary

All concentration statistics below use the processed `Microplastics Measurement` column.

| Statistic | Value |
| --- | ---: |
| Minimum concentration | 0.0 |
| Maximum concentration | 137,800.0 |
| Mean | 123.13759514591526 |
| Median | 0.213438 |
| Standard deviation | 1,917.3396018665717 |
| 25th percentile | 0.0139845 |
| 75th percentile | 1.5589884999999999 |

Coordinate ranges:

- Latitude: **-71.69904** to **89.7614**
- Longitude: **-179.97** to **179.854333**

### Observation count by region

| Region | Count |
| --- | ---: |
| Missing/NaN | 3,559 |
| Mediterranean Sea | 1,183 |
| Inner Seas off the West Coast of Scotland | 261 |
| North Sea | 255 |
| Gulf of America (formerly Gulf of Mexico) | 215 |
| Celtic Sea | 147 |
| Philippine Sea | 129 |
| Coral Sea | 105 |
| South China Sea | 100 |
| Bay of Bengal | 96 |
| Tasman Sea | 90 |
| Laccadive Sea | 72 |
| Great Australian Bight | 48 |
| Caribbean Sea | 44 |
| Greenland Sea | 43 |
| Arabian Sea | 43 |
| Kara Sea | 42 |
| Laptev Sea | 39 |
| Bay of Biscay | 36 |
| Norwegian Sea | 35 |
| Black Sea | 34 |
| East China Sea | 30 |
| East Siberian Sea | 25 |
| Irish Sea and St. George's Channel | 22 |
| Mozambique Channel | 20 |
| Davis Strait | 19 |
| Arafura Sea | 18 |
| English Channel | 17 |
| Andaman Sea | 15 |
| Barentsz Sea | 15 |
| Baltic Sea | 14 |
| Northwestern Passages | 14 |
| Timor Sea | 11 |
| Gulf of St. Lawrence | 11 |
| Baffin Bay | 9 |
| Bering Sea | 6 |
| Solomon Sea | 6 |
| White Sea | 5 |
| Beaufort Sea | 5 |
| Barents Sea | 4 |
| Kattegat | 4 |
| Skagerrak Strait | 3 |
| Labrador Sea | 3 |
| Halmahera Sea | 3 |
| Chukchi Sea | 2 |
| Rio de La Plata | 2 |
| Bismarck Sea | 2 |
| Sulu Sea | 2 |
| Celebes Sea | 1 |

### Observation count by ocean

| Ocean | Count |
| --- | ---: |
| Atlantic Ocean | 3,474 |
| Pacific Ocean | 2,543 |
| Indian Ocean | 484 |
| Arctic Ocean | 353 |
| Southern Ocean | 13 |

### Observation count by year

| Year | Count |
| --- | ---: |
| 2010 | 315 |
| 2011 | 591 |
| 2012 | 644 |
| 2013 | 973 |
| 2014 | 534 |
| 2015 | 790 |
| 2016 | 368 |
| 2017 | 454 |
| 2018 | 616 |
| 2019 | 589 |
| 2020 | 261 |
| 2021 | 264 |
| 2022 | 234 |
| 2023 | 141 |
| 2024 | 93 |

### Observation count by month

| Month | Count |
| --- | ---: |
| January | 579 |
| February | 421 |
| March | 338 |
| April | 481 |
| May | 400 |
| June | 661 |
| July | 739 |
| August | 962 |
| September | 574 |
| October | 833 |
| November | 551 |
| December | 328 |

## Findings

- The raw file contains no `Study Type` column.
- Region metadata is missing for 3,559 processed records; these records remain valid for geographic and ocean-level analysis because latitude, longitude, date, measurement, and unit are present.
- The concentration distribution is highly right-skewed: the median is 0.213438 while the maximum is 137,800.0.
- The processed dataset satisfies the required filtering and validity checks.
- No data fabrication or expected-value substitution was used.
