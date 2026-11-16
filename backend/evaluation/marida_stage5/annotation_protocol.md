# Expert annotation protocol for an independent Sentinel-2 marine-debris benchmark

## Scene selection and blinding

Select genuine Sentinel-2 L2A products from multiple coasts, seasons, turbidity regimes, river plumes, harbors, and offshore fronts. Include both suspected debris and deliberately selected difficult negatives. Retain full SAFE/STAC metadata, product ID, acquisition UTC, tile geometry, cloud percentage, processing baseline, quantification value, band offsets, and checksums. Keep sites and acquisition dates disjoint across train, validation, and locked test partitions. Do not use MARIDA-derived patches as independent observations.

## Imagery and interface

Show co-registered B4/B3/B2 natural color, B8/B4/B3 false color, B11/B8/B4, floating-debris indices as optional context, and individual visible/NIR/SWIR spectra. Preserve original reflectance values and per-band masks. The annotation interface must display scale, north arrow, acquisition/product metadata, and allow polygon/point labels, confidence, uncertainty polygons, and comments. Never display model predictions during first-pass annotation.

## Label ontology

Primary positive class: visible floating anthropogenic debris at the Sentinel-2 spatial support, including mixed litter accumulations where plastic is confirmed or probable. Record plastic certainty separately (confirmed / probable / unknown). Explicit negative classes: water; ships and wakes; foam/whitecaps; natural organic material/wood; dense and sparse Sargassum or other algae; sediment/turbidity; cloud/cloud shadow/haze; shoreline/land. Use an `uncertain` label for mixed/ambiguous objects and exclude uncertain pixels from headline accuracy while reporting their area and frequency.

## Independent annotation and adjudication

Two trained marine remote-sensing annotators independently label each candidate scene using imagery and independent contemporaneous evidence when available (field reports, deployed targets, geotagged photographs, or very-high-resolution reference acquired near the Sentinel-2 time). Do not use model-generated predictions as reference. Annotators record class, confidence (high/medium/low), polygon/point geometry, and evidence source. A third expert adjudicates disagreements without seeing model outputs. Report class-wise agreement, Dice/IoU on overlapping polygons, point agreement within a predeclared positional tolerance, and Cohen's kappa for categorical samples. Keep original annotations, adjudications, and revision history immutable and versioned.

## Evaluation lock

Before any inference, freeze the checkpoint hash, preprocessing, class map, Strategy A 0.40, Strategy B 0.35, and temperature T=0.6118. Score Strategy A and B only at valid labeled support; report A abstentions separately. Strategy B override pixels must be tabulated by the original argmax class and verified for false debris labels. Bootstrap whole acquisition scenes (and, if enough sites, sites as the outer cluster); never bootstrap pixels as independent samples. Publish per-scene data and confidence intervals. Keep final external test scenes inaccessible until all analysis code and decisions are frozen.
