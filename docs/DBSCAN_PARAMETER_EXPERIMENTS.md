# DBSCAN Parameter Experiments

Generated from `backend/data/processed/ocean_water_clean.csv` by
`backend/scripts/run_dbscan_parameter_experiments.py`.

## Method

- Input observations: **6867**
- Coordinate fields: `Latitude (degree)` and `Longitude (degree)`
- Distance: geographic Haversine distance on a sphere
- Earth radius used for conversion: **6371.0 km**
- Grid: eps values `[50, 100, 150, 200, 250, 300, 400]` and min_samples values `[5, 10, 15, 20]`
- Total configurations: **28**

Compactness is measured as the mean and median great-circle distance from each
cluster member to that cluster's geographic centroid. It is a spatial quality
indicator, not a scientific validation metric.

## Results

| eps_km | min_samples | number_of_clusters | number_of_noise_points | noise_percentage | minimum_cluster_size | maximum_cluster_size | mean_cluster_size | median_cluster_size | largest_cluster_percentage | mean_centroid_distance_km | median_centroid_distance_km |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 50 | 5 | 256 | 2185 | 31.8188 | 3 | 807 | 18.2891 | 7.0 | 11.7519 | 81.5319 | 33.3005 |
| 50 | 10 | 78 | 3684 | 53.6479 | 9 | 538 | 40.8077 | 17.0 | 7.8346 | 81.1999 | 45.8876 |
| 50 | 15 | 49 | 4169 | 60.7106 | 9 | 405 | 55.0612 | 26.0 | 5.8978 | 72.603 | 46.1585 |
| 50 | 20 | 35 | 4623 | 67.322 | 21 | 215 | 64.1143 | 43.0 | 3.1309 | 46.9867 | 36.6654 |
| 100 | 5 | 186 | 1197 | 17.4312 | 5 | 1152 | 30.4839 | 8.0 | 16.7759 | 257.8706 | 152.8346 |
| 100 | 10 | 75 | 2336 | 34.0178 | 6 | 1074 | 60.4133 | 22.0 | 15.64 | 236.78 | 139.1858 |
| 100 | 15 | 57 | 2819 | 41.0514 | 15 | 1001 | 71.0175 | 28.0 | 14.577 | 162.2987 | 110.0324 |
| 100 | 20 | 51 | 3132 | 45.6094 | 20 | 947 | 73.2353 | 35.0 | 13.7906 | 145.1748 | 99.7816 |
| 150 | 5 | 149 | 787 | 11.4606 | 5 | 2278 | 40.8054 | 8.0 | 33.1731 | 546.11 | 367.8436 |
| 150 | 10 | 61 | 1703 | 24.7998 | 10 | 1161 | 84.6557 | 25.0 | 16.9069 | 337.188 | 258.2483 |
| 150 | 15 | 52 | 1984 | 28.8918 | 8 | 1152 | 93.9038 | 26.5 | 16.7759 | 327.5829 | 254.441 |
| 150 | 20 | 38 | 2328 | 33.9013 | 20 | 1150 | 119.4474 | 36.0 | 16.7468 | 329.8928 | 262.2538 |
| 200 | 5 | 107 | 585 | 8.519 | 4 | 2627 | 58.7103 | 8.0 | 38.2554 | 792.2519 | 701.0179 |
| 200 | 10 | 55 | 1231 | 17.9263 | 8 | 2345 | 102.4727 | 24.0 | 34.1488 | 676.9845 | 683.7016 |
| 200 | 15 | 40 | 1646 | 23.9697 | 15 | 1173 | 130.525 | 45.5 | 17.0817 | 406.2253 | 311.7794 |
| 200 | 20 | 34 | 1910 | 27.8142 | 14 | 1168 | 145.7941 | 52.5 | 17.0089 | 388.7231 | 306.1286 |
| 250 | 5 | 86 | 376 | 5.4755 | 4 | 2774 | 75.4767 | 11.0 | 40.3961 | 959.3263 | 834.2055 |
| 250 | 10 | 49 | 901 | 13.1207 | 8 | 2569 | 121.7551 | 32.0 | 37.4108 | 855.6347 | 769.2235 |
| 250 | 15 | 39 | 1294 | 18.8437 | 14 | 2368 | 142.8974 | 41.0 | 34.4838 | 776.3499 | 760.6034 |
| 250 | 20 | 32 | 1638 | 23.8532 | 18 | 1181 | 163.4062 | 51.0 | 17.1982 | 467.6463 | 352.3413 |
| 300 | 5 | 72 | 291 | 4.2377 | 5 | 2945 | 91.3333 | 12.0 | 42.8863 | 1057.6983 | 890.7094 |
| 300 | 10 | 44 | 738 | 10.7471 | 10 | 2718 | 139.2955 | 28.0 | 39.5806 | 945.1146 | 841.305 |
| 300 | 15 | 35 | 1010 | 14.708 | 9 | 2514 | 167.3429 | 54.0 | 36.6099 | 836.3367 | 811.9468 |
| 300 | 20 | 33 | 1348 | 19.6301 | 18 | 2380 | 167.2424 | 43.0 | 34.6585 | 786.182 | 772.7381 |
| 400 | 5 | 54 | 196 | 2.8542 | 4 | 3030 | 123.537 | 22.5 | 44.1241 | 1135.6793 | 972.2684 |
| 400 | 10 | 44 | 466 | 6.7861 | 7 | 2988 | 145.4773 | 26.0 | 43.5125 | 1082.5818 | 948.9906 |
| 400 | 15 | 31 | 760 | 11.0674 | 13 | 2795 | 197.0 | 61.0 | 40.7019 | 1003.6802 | 899.0348 |
| 400 | 20 | 29 | 915 | 13.3246 | 23 | 2681 | 205.2414 | 64.0 | 39.0418 | 934.7598 | 858.5729 |

## Visualizations

- [eps versus cluster count](figures/dbscan_eps_vs_clusters.png)
- [eps versus noise percentage](figures/dbscan_eps_vs_noise.png)
- [min_samples versus cluster count](figures/dbscan_min_samples_vs_clusters.png)

## Empirical selection

The selected configuration is **eps_km=150,
min_samples=10**. It was selected based on empirical
parameter sensitivity analysis, considering noise percentage, non-trivial cluster
sizes, geographic compactness, avoidance of one dominant cluster, and avoidance of
near-total noise. It was not selected solely by maximizing or minimizing cluster
count, and it is not claimed to be scientifically optimal.

Observed selected-configuration values:

- Clusters: **61**
- Noise points: **1703**
- Noise percentage: **24.7998%**
- Minimum cluster size: **10**
- Maximum cluster size: **1161**
- Mean cluster size: **84.6557**
- Median cluster size: **25.0**
- Largest cluster percentage: **16.9069%**
- Mean centroid distance: **337.188 km**
- Median centroid distance: **258.2483 km**

The selected values are stored in the configuration system as `DBSCAN_EPS_KM` and
`DBSCAN_MIN_SAMPLES`, with the current defaults set to the empirically selected
values. They can be overridden through environment variables.
