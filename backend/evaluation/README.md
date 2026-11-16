# MARIDA U-Net evaluation

This evaluation uses only the held-out `test_X.txt` members from official
MARIDA 1.0.0. It does not use a production satellite endpoint and does not
register research imagery in OceanWatch's site catalog.

## Dataset source and license

Obtain the original archive from the [official Zenodo record](https://doi.org/10.5281/zenodo.5151941),
not a repackaged detection dataset. The record identifies version 1.0.0, 1,381
256×256 Sentinel-2 patches, class and confidence masks, official train/validation/test
splits, and a published 1.2 GB ZIP MD5 of
`9bf32266f6e3711c9dfa3699b856c76f`. The archive expands to about 4.38 GB.
The dataset is distributed under CC BY 4.0; retain attribution and cite:

Kikaki, K., Kakogeorgiou, I., Mikeli, P., Raitsos, D. E., & Karantzalos, K.
(2022). MARIDA: A benchmark for Marine Debris detection from Sentinel-2 remote
sensing data. *PLOS ONE*, 17(1), e0262247. <https://doi.org/10.1371/journal.pone.0262247>

The upstream evaluation code is MIT licensed at
[`marine-debris/marine-debris.github.io`](https://github.com/marine-debris/marine-debris.github.io),
revision `8de83a3394edfbe867d9fa825439666369ec6282`.

## Download and verify on Windows PowerShell

From the `backend` directory:

```powershell
New-Item -ItemType Directory -Force data | Out-Null
python scripts\download_marida.py --workers 8
Expand-Archive -LiteralPath 'data/MARIDA.zip' -DestinationPath 'data' -Force
```

The downloader uses verified byte ranges and checks the exact size and MD5
`9bf32266f6e3711c9dfa3699b856c76f` before replacing the archive path. It keeps
resumable parts in `data/MARIDA.zip.parts` until verification succeeds. The
evaluator independently verifies this archive checksum when the archive is
retained. It also checks all official
split sizes (694/328/359), disjointness, the 1,381-member union, and image/mask
presence for every split entry.
The paper reports 194,843 annotated test pixels, while the checksum-verified
release masks contain 194,863 under the upstream `mask != 0` rule. The
evaluator records both counts and the 20-pixel difference instead of treating
the paper's reported count as a file-integrity failure.

## Run

```powershell
.\.venv-stage25\Scripts\python.exe scripts\evaluate_marida.py `
  --dataset-root data `
  --archive data\MARIDA.zip `
  --output-dir evaluation\marida_stage3
```

The script hashes and checks the unchanged checkpoint, reads the official test
split only, uses the checkpoint's band order and normalization, imputes
non-finite channels with the training mean, ignores mask value 0, aggregates
source labels 12–15 into Marine Water, and reports metrics on the sparse labeled
pixels. It compares local logits/probabilities/classes with a faithful upstream
U-Net implementation for every 256×256 test patch. A 256×256 input is divisible
by the network's 16-pixel downsampling factor, so no boundary padding is needed
for the official patches. OceanWatch's replicate-padding/cropping path for
nonstandard image dimensions is a local extension; the original upstream
network does not define that behavior.

Outputs include JSON and CSV metrics, the full confusion matrix, debris PR and
confidence analyses, per-scene metrics, upstream/local equivalence, and
representative prediction/false-positive/false-negative PNGs. Metrics describe
agreement with MARIDA's weak pixel labels; they are not object-level detection
accuracy, exhaustive debris absence, or geographic generalization claims.
